import QtQuick
import QtQml
import qs.Commons as Commons

Item {
    id: root
    Binding {
        target: Commons.Style
        property: "fontFamily"
        value: "Noto Sans"
        when: root.enabled
    }
    Component.onDestruction: root.enabled = false
}
