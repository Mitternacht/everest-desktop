import QtQuick
import QtQml
import qs.Commons as Commons

Item {
    Loader {
        id: plugin
        source: Qt.resolvedUrl("../../plugins/everest.typography/Service.qml")
    }
    Timer {
        interval: 100
        running: true
        onTriggered: {
            if (plugin.status !== Loader.Ready || Commons.Style.fontFamily !== "Noto Sans") {
                console.error("Typography plugin did not apply the proportional font");
                Qt.exit(1);
                return;
            }
            plugin.active = false;
            Qt.callLater(function() {
                if (Commons.Style.fontFamily !== "Original Mono") {
                    console.error("Typography plugin did not restore the original font");
                    Qt.exit(1);
                    return;
                }
                console.log("Typography applies and restores successfully");
                Qt.exit(0);
            });
        }
    }
}
