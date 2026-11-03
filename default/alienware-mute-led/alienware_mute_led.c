// SPDX-License-Identifier: GPL-2.0-only
/*
 * Speaker-mute and mic-mute key lamps on the Alienware x15 R2.
 *
 * The lamps are the BIOS "global mute" indicators that dell-laptop drives
 * through the Dell SMBIOS tokens GLOBAL_MUTE_ENABLE/DISABLE (0x058C/0x058D)
 * and GLOBAL_MIC_MUTE_ENABLE/DISABLE (0x0364/0x0365). dell-laptop never loads
 * on this machine, because its DMI table only accepts the sys_vendor
 * "Dell Inc." and "Dell Computer Corporation", while dell-smbios (which
 * accepts the "Alienware" OEM string) loads fine. This module registers just
 * the two LED class devices, with dell-laptop's names and default triggers,
 * and writes the tokens through dell-smbios.
 *
 * Reading a token back does not reflect the lamp on this BIOS, so the driver
 * never reads: it remembers the last brightness the LED core asked for and
 * writes it again on resume, in case the firmware reset the lamp.
 */

#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt

#include <linux/build_bug.h>
#include <linux/cleanup.h>
#include <linux/container_of.h>
#include <linux/device.h>
#include <linux/dmi.h>
#include <linux/err.h>
#include <linux/leds.h>
#include <linux/lockdep.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/platform_device.h>
#include <linux/pm.h>
#include <linux/stddef.h>
#include <linux/types.h>
#include <uapi/linux/wmi.h>

#define DRV_NAME "alienware-mute-led"

/*
 * From drivers/platform/x86/dell/dell-smbios.h (v7.2.8), which the kernel
 * build tree does not ship. struct calling_interface_buffer, CLASS_TOKEN_WRITE
 * and SELECT_TOKEN_STD come from the uapi header. Without CONFIG_MODVERSIONS
 * nothing checks these declarations at load time, so check-dell-smbios-abi
 * compares them with the target kernel's dell_smbios BTF before every build
 * (see Makefile), and aw_lookup() checks each token it gets back.
 */
#define GLOBAL_MIC_MUTE_ENABLE	0x0364
#define GLOBAL_MIC_MUTE_DISABLE	0x0365
#define GLOBAL_MUTE_ENABLE	0x058C
#define GLOBAL_MUTE_DISABLE	0x058D

struct calling_interface_token {
	u16 tokenID;
	u16 location;
	union {
		u16 value;
		u16 stringlength;
	};
};

void dell_fill_request(struct calling_interface_buffer *buffer,
		       u32 arg0, u32 arg1, u32 arg2, u32 arg3);
int dell_send_request(struct calling_interface_buffer *buffer,
		      u16 class, u16 select);
struct calling_interface_token *dell_smbios_find_token(int tokenid);

static bool force;
module_param(force, bool, 0444);
MODULE_PARM_DESC(force, "Load on a machine that is not in the DMI list (default: false)");

static bool mic = true;
module_param(mic, bool, 0444);
MODULE_PARM_DESC(mic, "Register platform::micmute for the mic-mute key (default: true)");

/* Only the model the token behaviour was tested on; force=1 loads elsewhere. */
static const struct dmi_system_id aw_mute_dmi_table[] __initconst = {
	{
		.ident = "Alienware x15 R2",
		.matches = {
			DMI_MATCH(DMI_SYS_VENDOR, "Alienware"),
			DMI_MATCH(DMI_PRODUCT_NAME, "Alienware x15 R2"),
		},
	},
	{ }
};
MODULE_DEVICE_TABLE(dmi, aw_mute_dmi_table);

struct aw_token {
	u16 id;
	u16 location;
	u16 value;
};

struct aw_lamp {
	struct led_classdev cdev;
	struct aw_token on;	/* written while muted */
	struct aw_token off;	/* written while not muted */
	/*
	 * The x15 R2 BIOS keeps these tokens at the location equal to their
	 * id; any other location means the token was read wrongly.
	 */
	bool location_is_id;
	enum led_brightness state;	/* last requested brightness, under aw_lock */
	bool registered;
};

enum { AW_SPEAKER, AW_MIC };

static int aw_led_set(struct led_classdev *cdev, enum led_brightness brightness);

static struct aw_lamp aw_lamps[] = {
	[AW_SPEAKER] = {
		.cdev = {
			.name = "platform::mute",
			.max_brightness = 1,
			.brightness_set_blocking = aw_led_set,
			.default_trigger = "audio-mute",
			.flags = LED_REJECT_NAME_CONFLICT,
		},
		.on.id = GLOBAL_MUTE_ENABLE,
		.off.id = GLOBAL_MUTE_DISABLE,
		.location_is_id = true,
	},
	[AW_MIC] = {
		.cdev = {
			.name = "platform::micmute",
			.max_brightness = 1,
			.brightness_set_blocking = aw_led_set,
			.default_trigger = "audio-micmute",
			.flags = LED_REJECT_NAME_CONFLICT,
		},
		.on.id = GLOBAL_MIC_MUTE_ENABLE,
		.off.id = GLOBAL_MIC_MUTE_DISABLE,
	},
};

/* Serialises token writes with the stored state of both lamps. */
static DEFINE_MUTEX(aw_lock);
static struct platform_device *aw_pdev;

/* Fill in a token's location and value, checking that it is the token asked for. */
static int aw_lookup(struct aw_token *t, bool location_is_id)
{
	const struct calling_interface_token *token = dell_smbios_find_token(t->id);

	if (!token)
		return -ENODEV;
	if (token->tokenID != t->id ||
	    (location_is_id && token->location != t->id)) {
		pr_warn("lookup of token %#06x returned token %#06x at location %#06x, not using it\n",
			t->id, token->tokenID, token->location);
		return -EIO;
	}
	t->location = token->location;
	t->value = token->value;
	return 0;
}

/* Write the ENABLE or DISABLE token that matches the lamp's stored state. */
static int aw_write(struct aw_lamp *lamp)
{
	const struct aw_token *t = lamp->state ? &lamp->on : &lamp->off;
	struct calling_interface_buffer buffer;
	int ret;

	lockdep_assert_held(&aw_lock);

	dell_fill_request(&buffer, t->location, t->value, 0, 0);
	ret = dell_send_request(&buffer, CLASS_TOKEN_WRITE, SELECT_TOKEN_STD);
	if (ret)
		pr_warn_ratelimited("%s: writing token %#06x failed: %d (output0 %d)\n",
				    lamp->cdev.name, t->id, ret, (s32)buffer.output[0]);
	return ret;
}

static int aw_led_set(struct led_classdev *cdev, enum led_brightness brightness)
{
	struct aw_lamp *lamp = container_of(cdev, struct aw_lamp, cdev);

	guard(mutex)(&aw_lock);
	lamp->state = brightness ? LED_ON : LED_OFF;
	return aw_write(lamp);
}

static int aw_resume(struct device *dev)
{
	unsigned int i;

	guard(mutex)(&aw_lock);
	for (i = 0; i < ARRAY_SIZE(aw_lamps); i++)
		if (aw_lamps[i].registered)
			aw_write(&aw_lamps[i]);
	return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(aw_pm_ops, NULL, aw_resume);

static int __init aw_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	unsigned int i, count = 0;
	int ret;

	for (i = 0; i < ARRAY_SIZE(aw_lamps); i++) {
		struct aw_lamp *lamp = &aw_lamps[i];

		if (i == AW_MIC && !mic)
			continue;

		ret = aw_lookup(&lamp->on, lamp->location_is_id);
		if (!ret)
			ret = aw_lookup(&lamp->off, lamp->location_is_id);
		if (ret == -ENODEV) {
			dev_info(dev, "%s: SMBIOS tokens %#06x/%#06x not present, skipping\n",
				 lamp->cdev.name, lamp->on.id, lamp->off.id);
			continue;
		}
		if (ret)
			return dev_err_probe(dev, ret, "SMBIOS token lookup failed\n");

		ret = devm_led_classdev_register(dev, &lamp->cdev);
		if (ret == -EEXIST) {
			dev_info(dev, "%s already exists, leaving that lamp to its driver\n",
				 lamp->cdev.name);
			continue;
		}
		if (ret)
			return dev_err_probe(dev, ret, "registering %s\n", lamp->cdev.name);

		/*
		 * Write the stored state once. If no trigger has set the LED
		 * yet, this clears a lamp the firmware left lit; if the
		 * trigger's write already ran, it repeats it; if that write is
		 * still queued, it follows this one. If the dell-smbios backend
		 * is not bound yet this fails, and the next trigger event (the
		 * attach helper causes one) writes the lamp again.
		 */
		scoped_guard(mutex, &aw_lock)
			aw_write(lamp);

		lamp->registered = true;
		count++;
		dev_info(dev, "registered %s: ENABLE %#06x (location %#06x value %u), DISABLE %#06x (location %#06x value %u)\n",
			 lamp->cdev.name,
			 lamp->on.id, lamp->on.location, lamp->on.value,
			 lamp->off.id, lamp->off.location, lamp->off.value);
	}

	return count ? 0 : -ENODEV;
}

static struct platform_driver aw_driver = {
	.driver = {
		.name = DRV_NAME,
		.pm = pm_sleep_ptr(&aw_pm_ops),
	},
};

static int __init aw_init(void)
{
	struct device *dell_laptop;

	/*
	 * struct calling_interface_token is checked by check-dell-smbios-abi
	 * before the build; these only hold the uapi buffer to the layout
	 * this file uses.
	 */
	BUILD_BUG_ON(sizeof(struct calling_interface_buffer) != 36);
	BUILD_BUG_ON(offsetof(struct calling_interface_buffer, input) != 4);
	BUILD_BUG_ON(offsetof(struct calling_interface_buffer, output) != 20);

	if (!dmi_check_system(aw_mute_dmi_table)) {
		if (!force)
			return -ENODEV;
		pr_warn("force=1: loading on a machine that is not in the DMI list\n");
	}

	/* Once dell-laptop supports the machine, it drives these lamps itself. */
	dell_laptop = bus_find_device_by_name(&platform_bus_type, NULL, "dell-laptop");
	if (dell_laptop) {
		put_device(dell_laptop);
		pr_info("dell-laptop is loaded and drives the mute lamps, not loading\n");
		return -ENODEV;
	}

	aw_pdev = platform_create_bundle(&aw_driver, aw_probe, NULL, 0, NULL, 0);
	return PTR_ERR_OR_ZERO(aw_pdev);
}

static void __exit aw_exit(void)
{
	/* Unbinding unregisters the LEDs, which writes both lamps off. */
	platform_device_unregister(aw_pdev);
	platform_driver_unregister(&aw_driver);
}

module_init(aw_init);
module_exit(aw_exit);

MODULE_DESCRIPTION("Alienware x15 R2 speaker and mic mute key lamps via Dell SMBIOS tokens");
MODULE_LICENSE("GPL");
