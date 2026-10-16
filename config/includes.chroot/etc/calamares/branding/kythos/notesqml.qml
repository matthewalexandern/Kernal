import QtQuick 2.7
import QtQuick.Controls 2.2

Item {
    Flickable {
        anchors.fill: parent
        anchors.margins: 24
        contentWidth: width
        contentHeight: information.implicitHeight
        clip: true
        ScrollBar.vertical: ScrollBar { }
        Text {
            id: information
            width: parent.width
            textFormat: Text.RichText
            wrapMode: Text.WordWrap
            font.pixelSize: 19
            color: "#17232b"
            text: qsTr("<h2>Choose the installation path you need</h2>"
                + "<p>This Calamares installer prepares the <b>KythOS Kernal common base</b>: a terminal system with the supported kernel, broad drivers and firmware, networking, SSH, encryption tools, and audit controls.</p>"
                + "<p><b>Partitioning is your choice:</b> use the native guided, alongside, replacement, or manual partitioning options. Guided installations suggest a 2 GiB boot partition and use the remaining selected space for the system. These are guided defaults; manual partitioning lets you choose your own sizes and mount points.</p>"
                + "<p><b>Encryption and boot:</b> LUKS2-encrypted root requires a separate unencrypted <b>/boot</b> for the supported signed GRUB chain. An unencrypted root can contain its own boot files. With root encryption, use encrypted swap partitions, a swap file inside encrypted root, or no swap. The native partition page checks these boot requirements before proceeding.</p>"
                + "<p>The ISO also retains the advanced graphical and text installer as an alternative installation path.</p>"
                + "<p><b>Encryption:</b> store your passphrase safely. TPM2 enrollment is an optional post-install step using <b>kythos-enroll-tpm2</b>, with a tested recovery passphrase required.</p>"
                + "<p>The temporary live desktop and installer are removed from the installed common base. <b>Log in automatically</b> on the Users page is optional and applies to the local terminal on tty1. It is off by default; SSH still requires your password or key. Desktop, server, hypervisor, and AI editions build on this same foundation.</p>")
        }
    }
}
