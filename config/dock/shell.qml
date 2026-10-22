import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    id: root
    property var palette: ({
        background: "#1c1c1e",
        foreground: "#f2f2f7",
        accent: "#7ab8ff"
    })
    readonly property var windows: ToplevelManager.toplevels.values
    readonly property var active: ToplevelManager.activeToplevel
    readonly property var items: buildItems()

    function normalized(value) {
        return String(value || "").toLowerCase().replace(/\.desktop$/, "");
    }

    function buildItems() {
        // Reading active also refreshes the delegates after compositor focus changes.
        const activeWindow = active;
        const result = [
            { key: "apps", name: "Applications", icon: "view-app-grid-symbolic",
              aliases: [], command: ["omarchy-menu", "toggle", "apps"], windows: [] },
            { key: "files", name: "Files", icon: "system-file-manager",
              aliases: ["org.gnome.nautilus", "nautilus"],
              command: ["omarchy-launch-nautilus"], windows: [] },
            { key: "terminal", name: "Terminal", icon: "utilities-terminal",
              aliases: ["foot", "alacritty", "kitty", "com.mitchellh.ghostty"],
              command: ["xdg-terminal-exec"], windows: [] },
            { key: "browser", name: "Browser", icon: "web-browser",
              aliases: ["chromium", "firefox", "google-chrome", "brave-browser", "com.brave.browser"],
              command: ["omarchy-launch-browser"], windows: [] }
        ];
        for (const window of windows) {
            if (window.parent)
                continue; // Dialogs are represented by their parent app.
            const id = normalized(window.appId);
            const entry = DesktopEntries.heuristicLookup(window.appId);
            const desktopId = entry ? normalized(entry.id) : id;
            let item = result.find(candidate =>
                candidate.aliases.indexOf(id) >= 0 || candidate.aliases.indexOf(desktopId) >= 0);
            if (!item) {
                item = { key: id || window.title, name: entry ? entry.name : (window.appId || window.title || "Window"),
                    icon: entry ? entry.icon : "application-x-executable",
                    aliases: [id, desktopId], command: [], entry: entry, windows: [] };
                result.push(item);
            }
            item.windows.push(window);
        }
        return result;
    }

    function launch(item) {
        if (item.command.length)
            Quickshell.execDetached(item.command);
        else if (item.entry)
            item.entry.execute();
    }

    function activate(item) {
        if (!item.windows.length) {
            launch(item);
            return;
        }
        const current = item.windows.indexOf(active);
        item.windows[(current + 1) % item.windows.length].activate();
    }

    FileView {
        id: paletteFile
        path: Quickshell.env("HOME") + "/.local/state/omarchy/current/theme/everest-dock.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try {
                const value = JSON.parse(text());
                if (/^#[0-9a-f]{6}$/i.test(value.background)
                    && /^#[0-9a-f]{6}$/i.test(value.foreground)
                    && /^#[0-9a-f]{6}$/i.test(value.accent))
                    root.palette = value;
            } catch (error) {
                console.warn("Everest dock: keeping last valid palette", error);
            }
        }
    }
    // Omarchy swaps the current theme directory atomically. Polling covers replacement
    // of a watched directory without adding a theme hook or touching other themes.
    Timer {
        interval: 3000
        repeat: true
        running: true
        onTriggered: paletteFile.reload()
    }
    IpcHandler {
        target: "dock"
        function reloadTheme(): void { paletteFile.reload(); }
        function stop(): void { Qt.quit(); }
    }

    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: panel
            required property var modelData
            screen: modelData
            anchors.bottom: true
            margins.bottom: 10
            implicitWidth: Math.min(modelData.width - 24, row.implicitWidth + 24)
            implicitHeight: 78
            exclusiveZone: 88
            color: "transparent"
            WlrLayershell.namespace: "everest-dock"
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

            Rectangle {
                anchors.fill: parent
                radius: 20
                color: Qt.alpha(root.palette.background, 0.94)
                border.width: 1
                border.color: Qt.alpha(root.palette.foreground, 0.18)

                Flickable {
                    anchors.fill: parent
                    anchors.margins: 12
                    contentWidth: row.implicitWidth
                    contentHeight: height
                    clip: true
                    flickableDirection: Flickable.HorizontalFlick
                    boundsBehavior: Flickable.StopAtBounds
                    Row {
                        id: row
                        spacing: 4
                        Repeater {
                            model: root.items
                            Button {
                                id: appButton
                                required property var modelData
                                implicitWidth: 54
                                implicitHeight: 54
                                padding: 0
                                focusPolicy: Qt.NoFocus
                                Accessible.name: modelData.name + (modelData.windows.length ? ", running" : "")
                                ToolTip.visible: hovered
                                ToolTip.delay: 500
                                ToolTip.text: modelData.name + (modelData.windows.length
                                    ? " — " + modelData.windows.length + " window(s); click to cycle, right-click to launch"
                                    : " — click to launch")
                                onClicked: root.activate(modelData)
                                background: Rectangle {
                                    radius: 12
                                    color: appButton.hovered ? Qt.alpha(root.palette.accent, 0.18) : "transparent"
                                }
                                contentItem: Item {
                                    Image {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        y: 2
                                        width: 36
                                        height: 36
                                        source: Quickshell.iconPath(appButton.modelData.icon, "application-x-executable")
                                        sourceSize: Qt.size(36, 36)
                                        smooth: true
                                    }
                                    Rectangle {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        anchors.bottom: parent.bottom
                                        width: 5
                                        height: 5
                                        radius: 3
                                        visible: appButton.modelData.windows.length > 0
                                        color: appButton.modelData.windows.indexOf(root.active) >= 0
                                            ? root.palette.accent : root.palette.foreground
                                    }
                                }
                                TapHandler {
                                    acceptedButtons: Qt.RightButton
                                    onTapped: root.launch(appButton.modelData)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
