import QtQuick 2.7
import QtQuick.Controls 2.2

Rectangle {
    color: "#0c1522"

    Flickable {
        id: viewport
        anchors.fill: parent
        anchors.margins: 24
        contentWidth: width
        contentHeight: information.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        focus: true
        Keys.onPressed: function(event) {
            var step = 0
            if (event.key === Qt.Key_Down) step = 48
            else if (event.key === Qt.Key_Up) step = -48
            else if (event.key === Qt.Key_PageDown) step = height * 0.8
            else if (event.key === Qt.Key_PageUp) step = -height * 0.8
            else if (event.key === Qt.Key_Home) step = -contentHeight
            else if (event.key === Qt.Key_End) step = contentHeight
            else return
            contentY = Math.max(0, Math.min(Math.max(0, contentHeight - height), contentY + step))
            event.accepted = true
        }
        ScrollBar.vertical: ScrollBar { }

        Column {
            id: information
            width: viewport.width - 12
            spacing: 16

            Column {
                width: parent.width
                spacing: 8
                Text {
                    text: qsTr("YOUR INSTALLATION")
                    color: "#00d5e8"
                    font.family: "DejaVu Sans"
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.5
                }
                Text {
                    width: parent.width
                    text: qsTr("A foundation you control.")
                    color: "#f4faff"
                    font.family: "DejaVu Sans"
                    font.pixelSize: 29
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                }
                Text {
                    width: parent.width
                    text: qsTr("Choose your storage, protect your system, and build from one maintained common base.")
                    color: "#b5c6d5"
                    font.family: "DejaVu Sans"
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                    lineHeight: 1.2
                }
            }

            Grid {
                id: cards
                width: parent.width
                columns: width >= 630 ? 2 : 1
                spacing: 12
                property real cardWidth: (width - (columns - 1) * spacing) / columns
                Repeater {
                    model: [
                        {
                            number: "01", title: qsTr("Storage, your way"),
                            body: qsTr("Choose Use entire disk for automatic partitioning and mounting. It erases the selected disk. Manual partitioning lets you choose sizes and mount points. Alongside and replacement appear when available.")
                        },
                        {
                            number: "02", title: qsTr("Encryption with recovery"),
                            body: qsTr("LUKS2 is optional. Encrypted root needs a separate unencrypted /boot, plus encrypted swap or no swap. Keep your passphrase safe. Optional TPM2 enrollment comes after installation.")
                        },
                        {
                            number: "03", title: qsTr("Your account, your keys"),
                            body: qsTr("Set a password for recovery and SSH. After installation, enroll a FIDO2 key for local console login with kythos-fido-login. Automatic local login is optional and off by default.")
                        },
                        {
                            number: "04", title: qsTr("One base, four directions"),
                            body: qsTr("Start at a terminal with a maintained kernel, broad drivers and firmware, networking, SSH, and audit tools. Add your desktop, server, hypervisor, or AI stack. The live desktop is removed.")
                        }
                    ]
                    Rectangle {
                        width: cards.cardWidth
                        height: Math.max(176, cardContent.height + 36)
                        radius: 8
                        color: "#111f30"
                        border.color: "#263a50"
                        Column {
                            id: cardContent
                            x: 18
                            y: 18
                            width: parent.width - 36
                            spacing: 12
                            Row {
                                width: parent.width
                                spacing: 10
                                Rectangle {
                                    width: 28
                                    height: 25
                                    radius: 5
                                    color: "#173248"
                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.number
                                        color: "#83edf5"
                                        font.family: "DejaVu Sans"
                                        font.pixelSize: 11
                                        font.weight: Font.DemiBold
                                    }
                                }
                                Text {
                                    width: parent.width - 38
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.title
                                    color: "#f4faff"
                                    font.family: "DejaVu Sans"
                                    font.pixelSize: 16
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.WordWrap
                                }
                            }
                            Text {
                                width: parent.width
                                text: modelData.body
                                color: "#b5c6d5"
                                font.family: "DejaVu Sans"
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                                lineHeight: 1.2
                            }
                        }
                    }
                }
            }

            Text {
                width: parent.width
                text: qsTr("Review the full plan on Summary before the installer changes your disks.")
                color: "#8da2b6"
                font.family: "DejaVu Sans"
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                lineHeight: 1.2
                bottomPadding: 12
            }
        }
    }
}
