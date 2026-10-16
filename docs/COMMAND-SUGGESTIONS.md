# Command suggestions

KythOS includes an original, local command helper for interactive Bash. It
discovers installed executable names from PATH, indexes packaged manuals as
data, and preserves Bash's native completion. A reviewed phrase catalogue
adds common administrative requests.

New executable names are discovered from the installed system. Contextual
options and command declarations come from local package documentation.
This is deterministic local help, not a general natural-language interpreter
or a cloud model that can infer arbitrary shell programs.

## Using the helper

Type a phrase, then press **Tab** to request a suggestion. When a suggestion is
shown, **Tab** or **Right Arrow** copies it to the command line. Review or edit
the command, then press **Enter** to execute it through the ordinary shell.
Arrow keys do not execute commands. Up and Down retain their history behavior.
When no KythOS suggestion applies, normal shell completion remains available.

Press **F1** to describe the current command without changing or executing the
line. External commands use available local manual metadata; builtins use
Bash's own usage text. Aliases and functions receive a short inspection hint
and keep their own behavior. Existing custom F1 bindings take precedence.

`kythos-help systemctl` provides the same local lookup outside the editing
buffer. `kythos-help list processes` searches command descriptions.
Commands without packaged documentation are still discovered; the helper
reports missing metadata and leaves normal execution and completion available.
Full syntax remains available through `man COMMAND`.

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

Spelling suggestions apply to executable names throughout the installed PATH,
including an explicit `sudo COMMAND` form. Documented flag suggestions are
conservative: only an immediately following long option can be corrected,
because a later option-looking word may be another option's literal value.
Recognized command declarations can supply subcommand suggestions where the
manual structure establishes them. Incomplete or ambiguous matches stay as
hints; the helper does not invent a command-specific argument grammar.

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

The root-owned index is `/var/cache/kythos/command-index.json`. It is generated
in the image and refreshed after package transactions through an APT hook.
It contains executable and documentation metadata, with no typed commands or
shell history. To refresh after manual package or documentation changes, run:

```sh
sudo /usr/local/libexec/kythos-command-suggest --refresh-index
```

Indexing reads bounded manual files, following only data-only man-page links
inside `/usr/share/man`. Roff macros and inspected executables are never run.
Corrupt or unavailable metadata falls back to ordinary shell behavior. The
index and helper source are shared by amd64 and ARM64 builds.

The matching engine, catalogue, bindings and tests accompany the complete
editable recipe on the source ISO under the project's MIT license.
