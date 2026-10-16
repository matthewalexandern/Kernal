# Command suggestions

KythOS includes an original, local phrase and typo suggestion helper for
interactive Bash. It uses a reviewed action catalogue and bounded spelling
matching. It is not a general natural-language interpreter or a cloud service.
Its supported phrases can be extended without listing every misspelling.

## Using the helper

Type a phrase, then press **Tab** to request a suggestion. When a suggestion is
shown, **Tab** or **Right Arrow** copies it to the command line. Review or edit
the command, then press **Enter** to execute it through the ordinary shell.
Arrow keys do not execute commands. Up and Down retain their history behavior.
When no KythOS suggestion applies, normal shell completion remains available.

Examples of supported requests include:

```text
ssh copy di
sshcopyid 192.0.2.10
change matthew's password
change password matthew
create user matthew
make matthew an admin
add matthew to administrators
refresh package lists
show hardware
```

Missing or ambiguous details produce a short hint rather than an executable
guess. For example, `change password` needs an account name, and `add matthew
to root users` needs clarification. Administrator access means membership in
the configured administrative group; the helper does not create UID-zero
accounts. Existing account names, hostnames, paths and package names are not
silently corrected.

The first version supports Bash's default Emacs editing mode. Vi mode and
custom Tab bindings are left available to their existing handlers. The helper
does not execute suggested commands, collect passwords, read shell
history or send typed text to a network service. Authentication and permission
checks remain with the actual commands and sudo. Scripts and noninteractive
shells retain their normal behavior.

## Configuration and source

Set `KYTHOS_SUGGESTIONS=0` before starting Bash to disable the integration:

```sh
KYTHOS_SUGGESTIONS=0 bash
```

Run `kythos_suggestions_off` to restore the original bindings in the current
shell. Any bindings subsequently customized by the user remain in place.

The engine is `/usr/local/libexec/kythos-command-suggest`, the reviewed
catalogue is `/usr/share/kythos/command-intents.json`, and the interactive
integration is `/etc/profile.d/60-kythos-suggestions.sh`. The system Bash
configuration loads the same guarded integration for non-login terminals.
User Bash configuration is read afterward and may override key bindings.

The matching engine, catalogue, bindings and tests accompany the complete
editable recipe on the source ISO under the project's MIT license.
