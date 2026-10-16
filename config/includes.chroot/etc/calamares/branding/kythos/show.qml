import QtQuick 2.7
import calamares.slideshow 1.0

Presentation {
    id: presentation
    Rectangle { anchors.fill: parent; color: "#0c1522"; z: -1 }
    Timer {
        interval: 14000
        running: presentation.activatedInCalamares
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }
    Slide {
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: "#0c1522" }
        Column {
            anchors.centerIn: parent
            width: parent.width * 0.82
            spacing: 22
            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 110
                height: 100
                fillMode: Image.PreserveAspectFit
                source: "kythos-logo.png"
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: qsTr("Built on a maintained foundation.")
                color: "#f4faff"
                font.family: "DejaVu Sans"
                font.pixelSize: 27
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: qsTr("A supported kernel. Broad drivers and firmware.\nOne common base for the system you want to build.")
                color: "#b5c6d5"
                font.family: "DejaVu Sans"
                font.pixelSize: 16
                wrapMode: Text.WordWrap
                lineHeight: 1.3
            }
        }
    }
    Slide {
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: "#0c1522" }
        Column {
            anchors.centerIn: parent
            width: parent.width * 0.82
            spacing: 24
            Text {
                text: qsTr("SECURITY YOU CAN INSPECT")
                color: "#00d5e8"
                font.family: "DejaVu Sans"
                font.pixelSize: 12
                font.weight: Font.DemiBold
                font.letterSpacing: 1.5
            }
            Text {
                width: parent.width
                text: qsTr("Know what your system is doing.")
                color: "#f4faff"
                font.family: "DejaVu Sans"
                font.pixelSize: 29
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                text: qsTr("Audit logging and file integrity tools give you a starting point. After installation, run kythos-security-status to review the controls and their current state.")
                color: "#b5c6d5"
                font.family: "DejaVu Sans"
                font.pixelSize: 17
                wrapMode: Text.WordWrap
                lineHeight: 1.3
            }
        }
    }
    Slide {
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: "#0c1522" }
        Column {
            anchors.centerIn: parent
            width: parent.width * 0.82
            spacing: 24
            Text {
                text: qsTr("YOUR NEXT CHAPTER")
                color: "#00d5e8"
                font.family: "DejaVu Sans"
                font.pixelSize: 12
                font.weight: Font.DemiBold
                font.letterSpacing: 1.5
            }
            Text {
                width: parent.width
                text: qsTr("Start lean. Make it yours.")
                color: "#f4faff"
                font.family: "DejaVu Sans"
                font.pixelSize: 29
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                text: qsTr("Your installed base opens at the terminal. Use cy to manage packages, kythos-hardware-status to inspect detected devices, and kythos-fido-login to enroll a security key for local login.")
                color: "#b5c6d5"
                font.family: "DejaVu Sans"
                font.pixelSize: 17
                wrapMode: Text.WordWrap
                lineHeight: 1.3
            }
        }
    }
}
