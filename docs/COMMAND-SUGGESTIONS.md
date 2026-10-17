# Offline command assistance

KythOS provides an extensible local assistance layer for interactive Bash and
an explicit `kythos-assist` command. It discovers executable names from the
current PATH, reads installed manual declarations as data, and uses the current
shell's builtin, keyword, alias, function and completion names. Newly installed
commands do not need entries in a maintained command-name list.

The helper never executes the command being inspected, including its
`--help` or `--version` options. Scripts can perform real work even when given
those options. It never executes a proposed command, changes an existing
command automatically, reads history or sends terminal data to a service.
There is no AI backend or network requirement. Missing documentation and
unsupported shell grammar produce uncertainty instead of invented flags.

## Interactive use

**Tab** previews a recognized typo or reviewed administrative phrase. A second
**Tab** or **Right Arrow** copies the pending proposal into the edit buffer.
Review or edit it, then use ordinary **Enter** to execute it. For example,
`sshcopyid user@host` and `ssh-copy-Id user@host` propose `ssh-copy-id user@host`.
Only the name changes; user names, targets and argument values are preserved.

**F1** inspects the current line without changing or executing it. Builtins use
Bash's own usage text. Aliases and functions are identified without displaying
their definitions, which can contain secrets. Existing custom F1 bindings take
precedence. Up/Down history, cursor movement and native filename/programmable
completion remain available. See [terminal navigation](CONSOLE.md)
for the independent history and output-scrollback controls.

The explicit interface works with vi mode, custom Tab bindings and disabled
suggestions. Quote a whole shell expression when inspecting pipelines:

```sh
kythos-assist --explain 'ls --all ./documents | grep invoice > matches.txt'
kythos-assist --complete 'systemctl --no'
kythos-assist --complete 'git comm'
kythos-assist --intent 'show network interfaces'
kythos-assist --intent 'compress files'
kythos-assist --diagnose --status 127 'missing-tool argument'
kythos-assist --json --explain 'ssh -v user@host'
kythos-help systemctl
kythos-help list processes
```

`--explain` is the default. `--complete` prints local candidate names without
inserting them. `--intent` first checks the reviewed phrase catalogue and typo
engine, then searches installed command descriptions. Description matches are
leads for manual review; they do not establish arbitrary argument syntax.
`--diagnose --status N` explains the explicitly supplied status and inspects
the command context. A nonzero status alone cannot determine a failure cause;
no prior output is collected and no error text is silently sent elsewhere.

In interactive Bash the function adds names and completion metadata from the
actual shell. The standalone executable and `kythos-help` can inspect PATH and
documentation, but cannot inspect the parent shell's unexported definitions.
For builtin details, use `help COMMAND`; for deliberately inspecting a shell
definition, use `type COMMAND`.

## Grounding, syntax and limits

The engine uses a bounded root-controlled system index generated from local
manual pages. It verifies executable identity and timestamps, the manual file,
and every followed `.so` data include before reusing metadata. Changed binaries,
manuals, removed commands and PATH shadows invalidate old declarations. A
missing or stale record triggers bounded direct manual lookup for that resolved
executable. Standard system commands use `/usr/share/man`; commands in another
`PREFIX/bin` or `PREFIX/sbin` can use `PREFIX/share/man`. A system manual is not
attached to an unrelated user executable with the same name.

Where available, the fixed root-controlled Debian package database reader
provides the installed package/version. The engine does not claim an upstream
runtime version when that evidence is unavailable. It reads declared options,
command descriptions, flag explanations and subcommands from the installed
manual, including separate subcommand manuals when the parent declares that
subcommand. Full local syntax remains available with `man COMMAND`.

Bash completion metadata contributes literal `complete -W` words and records
whether dynamic completion is available. The helper does not invoke `-F` or
`-C` callbacks or evaluate word-list substitutions. Native Tab retains the
normal behavior of those completions. Shell aliases/functions take precedence
over same-name packaged metadata; `command`, `builtin` and simple `sudo`
wrappers are distinguished for inspection.

The literal inspector recognizes quoting, empty arguments, escaped characters,
pipelines, conditionals, redirections and adjacent file-descriptor numbers.
It explains descriptor duplication, output truncation, pipeline status and the
fact that shell redirection permissions do not become privileged merely
because the command uses sudo. It checks only explicit path arguments for
existence/read permission in the current directory context; it does not read
file contents or enumerate directory contents. These checks are observations,
not a guarantee about permissions or state at eventual execution time.

Substitutions, variable expansion, globbing, compound constructs,
here-documents, incomplete quoting and complex wrapper argument grammars are
not evaluated. They receive explicit warnings. The helper is an inspector,
not a second Bash interpreter. It deliberately declines uncertain rewrites.
Flag typo correction is limited to the first argument because later
option-looking strings can be literal values. Neither paths, host names nor
account names are spell-corrected. Existing executables retain their meaning.

Typed command text and shell snapshots travel through an anonymous pipe and
are not saved. Snapshots contain names and completion declarations, not alias
expansions, function bodies, history or an environment dump. Explain/diagnose
output does not repeat arbitrary argument values. Correction previews are
suppressed for recognized password, credential, token, authorization and
credential-bearing URL forms. Secret detection cannot infer the meaning of
arbitrary positional values: enter secrets through the application's prompt
or another protected input mechanism rather than a command line.

## Configuration and extension

Set `KYTHOS_SUGGESTIONS=0` before starting Bash to disable automatic binding
integration, or run `kythos_suggestions_off` to restore this shell's previous
bindings. Later user binding changes are preserved. The explicit assistant
remains available. Noninteractive shells and scripts retain normal behavior.
Custom Tab bindings, vi mode and custom keymaps are left untouched.

The shared amd64/ARM64 implementation consists of:

- `/usr/local/libexec/kythos-command-suggest`: bounded discovery, data-only
  documentation indexing, proposal engine, syntax inspection and explicit CLI.
- `/etc/profile.d/60-kythos-suggestions.sh`: guarded Readline integration and
  anonymous-pipe shell context transport.
- `/usr/local/bin/kythos-assist` and `/usr/local/bin/kythos-help`: explicit entry
  points that also work outside the default shell.
- `/usr/share/kythos/command-intents.json`: a reviewed, schema-checked catalogue
  for selected administrative intents. General discovery is independent of it.

The system index `/var/cache/kythos/command-index.json` contains executable and
manual metadata only. The image generates it and an APT hook refreshes it after
package transactions. Manual package/documentation changes can be indexed with:

```sh
sudo /usr/local/libexec/kythos-command-suggest --refresh-index
```

Direct inspection still discovers a new command/manual before a refresh.
Description search uses the indexed inventory, so refresh it when adding
manually managed command documentation. Indexing reads bounded manual files
and follows only data includes within the selected man root. It does not run a
roff formatter, macro, included script, inspected executable or network tool.
The index rejects symlinks, nonregular files, unsafe ownership/modes and
malformed data. Corrupt or unavailable metadata leaves the shell usable.

To extend assistance, install the executable and a manual page declaring its
options and subcommands, and optionally provide normal Bash completions. Add
reviewed deterministic phrase transformations only when their argument types
and ambiguity behavior can be tested. Adding online AI later requires a
separate explicit data-access design; it is not necessary for this interface.

Behavioral tests use trap executables, disposable manuals and real Bash PTYs.
They cover new commands, shell definitions, completion callbacks, syntax,
uncertainty, status diagnosis, stale metadata, protected arguments, preview
acceptance and native editing behavior. Source tests do not replace acceptance
checks in installed amd64/ARM64 images and their actual terminals.
