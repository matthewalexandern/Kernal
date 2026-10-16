# Administrative tools remain discoverable from ordinary login shells.
# This changes command lookup only; privileged operations still require sudo.
: "${PATH:=/usr/local/bin:/usr/bin:/bin}"
for kythos_admin_directory in /usr/local/sbin /usr/sbin /sbin; do
    case ":$PATH:" in
        *:"$kythos_admin_directory":*) ;;
        *) PATH="$PATH:$kythos_admin_directory" ;;
    esac
done
unset kythos_admin_directory
export PATH
