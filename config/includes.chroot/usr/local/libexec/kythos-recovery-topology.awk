# Accept only a direct disk or partition backed by exactly one physical disk.
# Every input record comes from: lsblk -snP -o TYPE,RM,TRAN DEVICE
BEGIN {
    if (source_type != "disk" && source_type != "part") {
        unsafe = 1
    }
    if (forward_topology != "TYPE=\"" source_type "\"") {
        unsafe = 1
    }
}

{
    if ($0 !~ /^TYPE="(disk|part)" RM="[01]" TRAN="[^"]*"$/) {
        unsafe = 1
    }
    if ($0 ~ /^TYPE="part" /) {
        partitions++
    }
    if ($0 ~ /^TYPE="disk" /) {
        disks++
        if ($0 ~ / RM="1" / ||
            $0 ~ / TRAN="(usb|firewire|ieee1394)"$/) {
            external_disks++
        }
    }
}

END {
    if (source_type == "disk" && partitions != 0) {
        unsafe = 1
    }
    if (source_type == "part" && partitions != 1) {
        unsafe = 1
    }
    exit(unsafe || disks != 1 || external_disks != 1 ? 1 : 0)
}
