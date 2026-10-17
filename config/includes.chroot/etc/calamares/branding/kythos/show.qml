import QtQuick 2.7
import calamares.slideshow 1.0

Presentation {
    id: presentation
    Rectangle { anchors.fill: parent; color: "#0b0b0b"; z: -1 }
    Timer {
        interval: 14000
        running: presentation.activatedInCalamares
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }
    Slide {
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: "#0b0b0b" }
        Column {
            anchors.centerIn: parent
            width: parent.width * 0.82
            spacing: 22
            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 110
                height: 100
                fillMode: Image.PreserveAspectFit
                source: "kythos-logo.svg"
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: qsTr("Built on a maintained foundation.")
                color: "#ffffff"
                font.family: "DejaVu Sans"
                font.pixelSize: 27
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: qsTr("KythOS Kernal™ 2027\nhttps://kythos.ai")
                color: "#c8c8c8"
                font.family: "DejaVu Sans"
                font.pixelSize: 16
                wrapMode: Text.WordWrap
                lineHeight: 1.3
            }
        }
    }
    Slide {
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: "#0b0b0b" }
        Column {
            anchors.centerIn: parent
            width: parent.width * 0.82
            spacing: 24
            Text {
                text: qsTr("SECURITY YOU CAN INSPECT")
                color: "#ffffff"
                font.family: "DejaVu Sans"
                font.pixelSize: 12
                font.weight: Font.DemiBold
                font.letterSpacing: 1.5
            }
            Text {
                width: parent.width
                text: qsTr("Know what your system is doing.")
                color: "#ffffff"
                font.family: "DejaVu Sans"
                font.pixelSize: 29
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                text: qsTr("Audit logging and file integrity tools give you a starting point. After installation, run kythos-security-status to review the controls and their current state.")
                color: "#c8c8c8"
                font.family: "DejaVu Sans"
                font.pixelSize: 17
                wrapMode: Text.WordWrap
                lineHeight: 1.3
            }
        }
    }
    Slide {
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: "#0b0b0b" }
        Column {
            anchors.centerIn: parent
            width: parent.width * 0.82
            spacing: 24
            Text {
                text: qsTr("YOUR NEXT CHAPTER")
                color: "#ffffff"
                font.family: "DejaVu Sans"
                font.pixelSize: 12
                font.weight: Font.DemiBold
                font.letterSpacing: 1.5
            }
            Text {
                width: parent.width
                text: qsTr("Start lean. Make it yours.")
                color: "#ffffff"
                font.family: "DejaVu Sans"
                font.pixelSize: 29
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                text: qsTr("Your ISO edition determines the installed desktop and services. Use kythos-assist for local command guidance, kythos-hardware-status to inspect devices, and WiFi to connect to a wireless network.")
                color: "#c8c8c8"
                font.family: "DejaVu Sans"
                font.pixelSize: 17
                wrapMode: Text.WordWrap
                lineHeight: 1.3
            }
        }
    }
}
