import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell

FloatingWindow {
    id: settings
    required property var palette
    implicitWidth: 640
    implicitHeight: 500
    title: "Everest Settings"
    color: palette.background
    visible: false

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 28
        spacing: 22
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "Settings"
                color: settings.palette.foreground
                font.family: "Noto Sans"
                font.pixelSize: 26
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }
            Button {
                text: "Close"
                font.family: "Noto Sans"
                onClicked: settings.visible = false
            }
        }
        GridLayout {
            columns: 4
            columnSpacing: 14
            rowSpacing: 14
            Layout.fillWidth: true
            Repeater {
                model: [
                    { name: "Appearance", icon: "preferences-desktop-theme",
                      command: ["omarchy-menu", "toggle", "style"] },
                    { name: "Displays", icon: "video-display",
                      command: ["omarchy-shell", "shell", "toggle", "omarchy.monitor"] },
                    { name: "Sound", icon: "audio-volume-high",
                      command: ["omarchy-shell", "shell", "toggle", "omarchy.audio"] },
                    { name: "Network", icon: "network-wireless",
                      command: ["omarchy-shell", "shell", "toggle", "omarchy.network"] },
                    { name: "Bluetooth", icon: "bluetooth",
                      command: ["omarchy-shell", "shell", "toggle", "omarchy.bluetooth"] },
                    { name: "Power", icon: "battery-good",
                      command: ["omarchy-shell", "shell", "toggle", "omarchy.power"] },
                    { name: "Notifications", icon: "preferences-system-notifications",
                      command: ["omarchy-shell", "notifications", "showHistory"] },
                    { name: "Lock Screen", icon: "system-lock-screen",
                      command: ["omarchy-system-lock"] }
                ]
                Button {
                    id: category
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredWidth: 130
                    Layout.preferredHeight: 116
                    Accessible.name: modelData.name
                    onClicked: {
                        settings.visible = false;
                        Quickshell.execDetached(modelData.command);
                    }
                    background: Rectangle {
                        radius: 14
                        color: category.hovered ? Qt.alpha(settings.palette.accent, 0.16)
                                                : Qt.alpha(settings.palette.foreground, 0.045)
                        border.width: 1
                        border.color: Qt.alpha(settings.palette.foreground, 0.10)
                    }
                    contentItem: Column {
                        spacing: 12
                        anchors.centerIn: parent
                        Image {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 34
                            height: 34
                            sourceSize: Qt.size(34, 34)
                            source: Quickshell.iconPath(category.modelData.icon, "preferences-system")
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: category.modelData.name
                            color: settings.palette.foreground
                            font.family: "Noto Sans"
                            font.pixelSize: 13
                        }
                    }
                }
            }
        }
        Item { Layout.fillHeight: true }
        Text {
            text: "Everest"
            color: Qt.alpha(settings.palette.foreground, 0.55)
            font.family: "Noto Sans"
            font.pixelSize: 12
            Layout.alignment: Qt.AlignHCenter
        }
    }
}
