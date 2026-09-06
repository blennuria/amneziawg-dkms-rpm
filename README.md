# amneziawg-rpm

RPM packaging for [AmneziaWG](https://docs.amnezia.org/documentation/amnezia-wg/)
on EL9 and EL10, built in GitHub Actions with mock.

Two packages come out of it:

| package | source | contents |
| --- | --- | --- |
| `amneziawg-dkms` (noarch) | [amneziawg-linux-kernel-module](https://github.com/amnezia-vpn/amneziawg-linux-kernel-module) | kernel module sources, rebuilt by DKMS on every kernel update |
| `amneziawg-tools` (x86_64) | [amneziawg-tools](https://github.com/amnezia-vpn/amneziawg-tools) | `awg`, `awg-quick`, `awg-quick@.service`, man pages, bash completion |

The upstream COPR (`amneziavpn/amneziawg`) has been stuck on 1.0.20241112
since November 2024, which is the 1.x module — these packages track the 3.x
branch. `amneziawg-dkms` keeps that COPR's `Epoch: 1`, so it upgrades cleanly
over a package installed from there.

## Install

```shell
# dkms itself lives in EPEL
sudo dnf install -y epel-release
sudo dnf install -y \
    https://github.com/<owner>/amneziawg-rpm/releases/latest/download/amneziawg-dkms-<nvr>.noarch.rpm \
    https://github.com/<owner>/amneziawg-rpm/releases/latest/download/amneziawg-tools-<nvr>.x86_64.rpm
```

`%posttrans` runs `dkms autoinstall` for the running kernel. If the machine has
no `kernel-devel` matching it (typical right after a kernel update, before the
reboot), the build is skipped with a warning — `dkms status` afterwards tells
you where things stand, and `/var/lib/dkms/amneziawg/<version>/build/make.log`
says why a build failed.

Both EL9 (5.14) and EL10 (6.12) kernels ship `CONFIG_WIREGUARD=m` and the
crypto library modules the module links against, so nothing else is needed.

### Secure Boot

Where the `dkms` package provides `/etc/dkms/sign_helper.sh` the module is
signed with a MOK generated under `/var/lib/dkms/`. Enrol it once:

```shell
sudo mokutil --import /var/lib/dkms/mok.pub
```

then reboot and accept the prompt in MokManager. The `%posttrans` scriptlet
prints this only when Secure Boot is on and the key is not enrolled yet.

### Usage

Same as `wg`/`wg-quick`, with the AmneziaWG obfuscation knobs (`Jc`, `Jmin`,
`Jmax`, `S1`, `S2`, `H1`–`H4`) in the `[Interface]` section:

```shell
sudo awg genkey | sudo tee /etc/amnezia/amneziawg/privatekey | awg pubkey
sudo $EDITOR /etc/amnezia/amneziawg/awg0.conf
sudo systemctl enable --now awg-quick@awg0
```

## Updating

Bump `Version:` in the spec of whichever component moved, add a `%changelog`
entry, and push a tag. Nothing else references the version — the workflow
takes the source URLs straight out of the specs.

Tags are `<version>-<release>` of **`amneziawg-dkms`** (e.g. `3.1.20260906-1`),
and the build refuses to publish if the tag and that spec disagree. The tools
carry their own upstream version and are rebuilt alongside; releasing a
tools-only update means bumping the dkms `Release:` and tagging that.

## CI

`.github/workflows/build.yml`:

1. **build** — mock builds SRPM + RPM for both specs in a CentOS Stream 9/10
   container.
2. **install-test** — installs the packages on the matching EL, builds the
   module against that release's `kernel-devel`, checks `modinfo` reports the
   packaged version, and smoke-tests `awg`.
3. **release** — on a tag, publishes the RPMs to a GitHub release. Debug and
   source packages stay in the run artifacts.

Only x86_64 is built. For aarch64, add a matrix entry on an `ubuntu-24.04-arm`
runner with the `-aarch64` mock config.
