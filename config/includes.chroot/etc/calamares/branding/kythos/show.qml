import QtQuick 2.0
import calamares.slideshow 1.0

Presentation {
    id: presentation
    Timer {
        interval: 12000
        running: true
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }
    Slide {
        Rectangle { anchors.fill: parent; color: "#071014" }
        Image {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: parent.height * 0.08
            width: parent.width * 0.42
            height: parent.height * 0.45
            fillMode: Image.PreserveAspectFit
            source: "kythos-logo.png"
        }
        Text {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: parent.height * 0.16
            width: parent.width * 0.88
            horizontalAlignment: Text.AlignHCenter
            color: "#d8e5eb"
            font.pixelSize: 23
            wrapMode: Text.WordWrap
            text: qsTr("KythOS Kernal\nOne common foundation for your next system.")
        }
    }
    Slide {
        Rectangle { anchors.fill: parent; color: "#071014" }
        Text {
            anchors.centerIn: parent
            width: parent.width * 0.85
            horizontalAlignment: Text.AlignHCenter
            color: "#d8e5eb"
            font.pixelSize: 23
            wrapMode: Text.WordWrap
            text: qsTr("Security you can inspect\nAudit logging, file integrity checks, and a supported kernel with broad driver support.")
        }
    }
    Slide {
        Rectangle { anchors.fill: parent; color: "#071014" }
        Text {
            anchors.centerIn: parent
            width: parent.width * 0.85
            horizontalAlignment: Text.AlignHCenter
            color: "#d8e5eb"
            font.pixelSize: 23
            wrapMode: Text.WordWrap
            text: qsTr("Your installed base starts at the terminal.\nUse cy to manage packages and kythos-security-status to inspect your system.")
        }
    }
}
