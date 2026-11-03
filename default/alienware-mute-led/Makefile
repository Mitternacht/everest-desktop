# SPDX-License-Identifier: GPL-2.0-only
ifneq ($(KERNELRELEASE),)
obj-m := alienware_mute_led.o

# alienware_mute_led.c declares dell-smbios's token struct and functions by
# hand, and nothing checks them at load time without CONFIG_MODVERSIONS, so
# every build (DKMS included) first compares them with the target kernel's
# BTF. A mismatch stops the build.
$(obj)/alienware_mute_led.o: | dell-smbios-abi
PHONY += dell-smbios-abi
dell-smbios-abi:
	@echo '  CHECK   dell-smbios ABI for $(KERNELRELEASE)'
	$(Q)bash $(src)/check-dell-smbios-abi $(KERNELRELEASE) $(objtree)
else
KDIR ?= /lib/modules/$(shell uname -r)/build

all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) modules

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) clean

.PHONY: all clean
endif
