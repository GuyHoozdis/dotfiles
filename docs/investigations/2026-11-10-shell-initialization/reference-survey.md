# Reference survey

Consulted 2026-11-10. This is a targeted read of documentation and selected startup
and installation files, not a full audit or an execution test. Linked branches
are mutable; conclusions describe the retrieved content, not future versions.
No upstream installer was executed or copied into this repository.

## References already in the root README

| Reference | Observed approach | Useful ideas | Limitations for these requirements |
|-----------|-------------------|--------------|-----------------------------------|
| [Paul Irish](https://github.com/paulirish/dotfiles) | Personal Bash/fish modules; symlink installer; separate machine setup scripts | Closest to edit-through-symlink workflow; current `.bash_profile` delegates to an interactively guarded `.bashrc` | Installer discovers a broad set of dotfiles and offers replacement of conflicts; not the proposed ownership-aware selective reset contract. `.bashrc` appends PATH entries, so its dispatch pattern alone does not guarantee idempotence |
| [Mathias Bynens](https://github.com/mathiasbynens/dotfiles) | Modular shell files, `.path`/`.extra`, rsync-based home deployment, separate macOS/Brew setup | Clear separation of personal additions and early PATH setup; useful individual settings | Copy deployment separates installed edits from source. Bootstrap pulls before copying; `.bash_profile` prepends `~/bin` without deduplication. No basis to adopt wholesale as a nested-login fix |
| [donnemartin/dev-setup](https://github.com/donnemartin/dev-setup) | Selectable setup sections dispatched by `.dots`, broad workstation provisioning, copied dotfiles | Explicitly says not to install everything; useful example of selecting capability groups | Documents testing on OS X 10.10/10.11. Scripts include privileged setup and download/copy deployment; not a current cross-platform reversible installer |
| [Kevin Elliott's gist](https://gist.github.com/kevinelliott/3135044) | OS X Mavericks rebuild checklist, package lists, separate dotfiles checkout sourced from a profile | A rebuild checklist can separate machine prerequisites from configuration | Historical machine recipe, not an installer architecture or safe current package list |
| [NPR developer environment](https://blog.apps.npr.org/2013/06/06/how-to-setup-a-developers-environment.html) | Team onboarding guide with staged manual steps | Human-readable prerequisites and recovery guidance matter alongside automation | Not a dotfiles deployment engine. Despite the 2013 URL, retrieved content reports a May 2025 update and uses uv; still Mac/team-specific and contains assumptions to review |
| [dotfiles.github.io](https://dotfiles.github.io/) | Directory of tutorials, managers, frameworks, and inspiration | Helps distinguish configuration content, deployment utilities, and bootstrap frameworks | A discovery index, not a single approach to evaluate or adopt |

### Selected source files checked

- Paul Irish: [login entrypoint](https://github.com/paulirish/dotfiles/blob/main/.bash_profile),
  [interactive rc](https://github.com/paulirish/dotfiles/blob/main/.bashrc),
  [symlink installer](https://github.com/paulirish/dotfiles/blob/main/symlink-setup.sh).
- Mathias Bynens: [bootstrap](https://github.com/mathiasbynens/dotfiles/blob/main/bootstrap.sh),
  [login configuration](https://github.com/mathiasbynens/dotfiles/blob/main/.bash_profile).
- dev-setup: [dispatcher](https://github.com/donnemartin/dev-setup/blob/master/.dots),
  [bootstrap](https://github.com/donnemartin/dev-setup/blob/master/bootstrap.sh).

## Management tools mentioned or useful for contrast

| Tool | What it provides | Fit and tradeoff |
|------|------------------|------------------|
| [GNU Stow](https://www.gnu.org/software/stow/manual/html_node/Invoking-Stow.html) | Package directories mirrored into a target tree using symlinks; simulation, unstow, restow, conflict detection | Preserves direct editing and enables selective packages. Adds Stow/Perl availability and a target-shaped layout. Does not install applications, fetch skills, or restore arbitrary overwritten files |
| [Dotbot](https://github.com/anishathalye/dotbot) | Declarative link/create/shell/clean directives; conditional links and backup options | Can map the current layout without a wholesale reorganization. Requires a Python runtime and adoption of its configuration/bootstrapping. Broken-link cleanup is not a complete uninstall/reset mechanism |
| [chezmoi](https://www.chezmoi.io/why-use-chezmoi/) | Source-to-target application, templates, machine variation, external sources, diff/dry-run | Stronger if rendered machine-specific config becomes a real requirement. Standard mode changes the immediate symlink-edit workflow; explicit apply/source-state concepts add overhead |

Stow is not a Git-sync replacement. It can coexist with the current `main` and
`cddotfiles` workflow; the question is whether automating selected links warrants
the dependency and layout convention. Set its target explicitly if the repo can
be cloned outside the home directory. Avoid adoption/overwrite features as a
default conflict policy. Review directory folding before using it with mixed,
tool-written configuration directories.

Dotbot describes itself as self-contained; this does not mean it runs without
Python. Its force/relink/backup options need deliberate policy choices.

chezmoi supports symlinks, including a symlink mode with limitations. It is not
correct to say it cannot preserve any symlinks. Its
[design documentation](https://www.chezmoi.io/user-guide/frequently-asked-questions/design/)
explains why its normal model writes target files and which source attributes
cannot use symlink mode.

## Synthesis

Borrow patterns rather than an entire personal workstation setup:
one-way login-to-interactive dispatch, small modules, explicit selections,
separate provisioning, and documented prerequisites.

The references do not establish that a complete overhaul is necessary. XDG
destinations, the repo's source layout, deployment tooling, and shell startup
semantics are independent choices. No manager makes a non-idempotent shell
startup sequence correct merely by installing its files.

## Provisioning and orchestration tools

Added in response to the user's follow-up on 2026-11-10. These tools operate at
a different layer from link managers, although they can create links themselves.
They can preserve the shared `main`, `cddotfiles`, and edit-through-symlink
workflow; adopting one does not require rendering every config as a template.

| Candidate | Model and potential fit | Costs and gaps | Evaluation priority |
|-----------|-------------------------|----------------|---------------------|
| Ansible | Desired-state modules and YAML playbooks/roles; local execution or SSH-based remote deployment; component selections, OS conditions, links, packages, and source checkout tasks | Python on the controller and generally on targets; collection/version management; minimal images need bootstrapping. Idempotence depends on modules/task design, not YAML alone. Check/diff support varies by module | Strong contender for fuller workstation provisioning and remote deployment |
| Chef Infra | Resource-based convergence using Ruby recipes/cookbooks; can manage packages, files, links, and OS-specific behavior. Local mode/chef-solo avoids needing Chef Infra Server | Chef runtime and cookbook/tooling lifecycle on managed machines; larger adoption cost for a few personal targets. Review current distribution, licensing, and platform support before a trial | Worth recording, but lower priority absent existing Chef expertise or a broader fleet-management need |
| Fabric + Invoke | Python task orchestration: Fabric supplies SSH/SFTP execution; Invoke supplies local execution and task CLI. Useful for coordinating deployment of selected components across hosts | Not a declarative configuration-management engine. We must implement state checks, idempotence, preview behavior, ownership, backups, and uninstall semantics ourselves | Useful if Python orchestration or remote fan-out is the primary need |

### What these tools do not settle

- Safe reset is not automatic rollback. Declaring a file/package absent does not
  restore an overwritten original or prove that this installation owns it.
  Removing a task from a playbook/recipe does not automatically undo its earlier
  effects. Backups and ownership need an explicit design.
- Ansible's agentless model does not mean zero target prerequisites, and check
  mode is not proof of a real install/uninstall round trip. Tasks explicitly
  configured to bypass check mode can still make changes.
- Chef does not inherently require a central server; local execution is a valid
  option. A server-based managed fleet would be a separate, larger choice.
- Fabric does not require installing Fabric on every SSH target, but commands it
  runs still depend on target tools. For local-only tasks, Invoke alone may be
  sufficient.
- None requires sudo for user-owned dotfile links. Privileged package/OS setup
  should remain explicit and separate from user configuration.
- Container/image builds should not need SSH or leave the orchestrator/runtime
  in the final image solely to provide `.inputrc`. A build-time deployment or
  small copy-based component path can coexist with workstation orchestration.
- All three can be exercised in Actions, but CI still needs real fixtures,
  repeat-run checks, collision cases, and teardown assertions.

### Proposed shortlist

For long-term evaluation, compare a small link/component installer, a link
manager, and Ansible against the same deployment scenarios. Keep Chef as a
documented alternative rather than building a full prototype immediately.
Evaluate Fabric/Invoke if a Python task API or multi-host orchestration becomes
a requirement; do not assume Python familiarity eliminates the maintenance cost
of a custom state-management layer.

No tool is selected. Ansible is more compelling as the scope grows from
"activate selected configs" to "rebuild selected workstation capabilities."
This does not change the recommendation to repair Bash independently first.

### Sources

- [Ansible introduction](https://docs.ansible.com/projects/ansible/latest/getting_started/introduction.html)
- [Ansible controller/target requirements](https://docs.ansible.com/projects/ansible/latest/installation_guide/intro_installation.html)
- [Ansible check/diff modes and limitations](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_checkmode.html)
- [Chef Infra 18 chef-solo/local execution](https://docs.chef.io/client/18/features/chef_solo/)
- [Fabric overview](https://www.fabfile.org/)
- [Fabric and Invoke responsibilities](https://docs.fabfile.org/en/stable/getting-started.html)

This is documentation-based evaluation, not an installed-tool trial. Current
Chef packaging/licensing and the exact supported-platform matrices remain
unverified; do not infer them from the local-mode documentation.
