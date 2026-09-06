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
# dkms itself lives in EPEL, and drags in gcc, make and the kernel-devel
# matching the running kernel
sudo dnf install -y epel-release

# file names from the latest release, e.g. for EL9:
base=https://github.com/blennuria/amneziawg-rpm/releases/latest/download
sudo dnf install -y \
    $base/amneziawg-dkms-3.1.20260906-1.el9.noarch.rpm \
    $base/amneziawg-tools-3.1.20260812-1.el9.x86_64.rpm
```

`%posttrans` runs `dkms install` for the running kernel (and honours
`/etc/dkms/no-autoinstall`). If the machine has no `kernel-devel` matching it
(typical right after a kernel update, before the reboot), the build is skipped
with a warning — `dkms status` afterwards tells
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
entry, and push a tag. Nothing else references the version — the workflow takes
the source URLs straight out of the specs.

Tags name the release, not a package: `YYYYMMDD` (`20260906.1` for a second one
the same day). The two components track separate upstreams with separate
version streams, so a tag can't stand for both — pinning it to one of them
would mean inventing a `Release:` bump for the other every time only it moved.
The versions actually shipped are in the release title, the notes and the file
names.

### Which versions pair up

Upstream tags the two repos with the same date on joint release days
(`v3.0.20260730`, `v3.0.20260805`, `v3.1.20260812`) and separately in between —
the kernel module has had three releases of its own since the last tools tag.
So take the newest tag of each and don't try to make the dates line up.

What has to match is the netlink API, not the version string: if the module
grows an attribute the tools don't know, `awg` silently cannot configure it.
The build compares the module's `src/uapi/wireguard.h` against the tools'
`src/uapi/linux/linux/wireguard.h` and fails when the attribute sets differ, so
a bump that outruns the other side is caught before anything ships. (The two
repos spell attribute 11 differently — `WGPEER_A_ADVANCED_SECURITY` versus
`WGPEER_A_AWG` — for the same value; the check folds one onto the other.)

The pair shipped here, module 3.1.20260906 with tools 3.1.20260812, is
byte-identical in that header to the last joint release. The seven module
commits since are internal: an uninitialised spinlock in `header_protection`,
`DisableCookies` and `RandomPaddingAddition` corrections, a fix for random
trailers on I1–I5 junk packets, and build fixes for kernel 7.1.5+.

## Patches

`0001-compat-probe-the-headers-for-backported-apis.patch` is the only local
change, and without it the module compiles on neither target. Upstream's
compat layer picks its shims from `LINUX_VERSION_CODE` alone, while EL kernels
backport APIs without moving that number:

- Stream 9 (5.14.0-741) has `timer_container_of` and no longer has
  `from_timer`, so every timer callback fails with
  `implicit declaration of function 'from_timer'`;
- Stream 10 (6.12.0-264) has `struct sockaddr_inet`, `netif_threaded_enable`
  and `struct rtnl_newlink_params`, each of which the compat layer defines a
  second time.

The patch turns those four into header probes in `compat/Kbuild.include`,
next to the ones already there for ptr_ring, siphash and dst_cache, so no
version numbers have to be kept up to date. Upstream PR
[#174](https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/pull/174)
fixes part of the same breakage for RHEL 10 by enumerating minor releases;
drop this patch if that or an equivalent lands upstream.

## Testing locally

The CI jobs are reproducible in a container — `podman`, `docker` or Apple's
`container`, with `--arch amd64` where the host is not x86_64:

```shell
container run --rm --arch amd64 -v "$PWD":/work quay.io/centos/centos:stream9 bash -c '
  dnf install -y --nogpgcheck epel-release
  dnf install -y --nogpgcheck --enablerepo=crb rpm-build rpmdevtools gcc make       systemd-rpm-macros dkms kernel-devel elfutils-libelf-devel
  rpmdev-setuptree && cp /work/*.spec ~/rpmbuild/SPECS/ && cp /work/*.patch ~/rpmbuild/SOURCES/
  spectool -g -C ~/rpmbuild/SOURCES ~/rpmbuild/SPECS/*.spec
  rpmbuild -ba ~/rpmbuild/SPECS/amneziawg-dkms.spec'
```

Then `dnf install` the results and drive the build with
`dkms install -m amneziawg -v <version> -k <kernel-devel version>`; in a
container `%posttrans` cannot do it for you, because `uname -r` is the host's
kernel.

## Why one repository

The packages come from two upstreams, but they are installed, upgraded and
tested as a pair: `awg-quick` is useless without the module and the module is
unreachable without `awg`. One repo means one release page holding a matching
set, one workflow, and one place to point a `createrepo` job at later. The cost
is that a change to either component republishes both — a few minutes of CI and
an unchanged package rebuilt under a new release tag, which is cheaper than
keeping two repositories in step by hand.

## CI

`.github/workflows/build.yml`:

1. **build** — checks that the two upstreams agree on the netlink API, then
   has mock build SRPM + RPM for both specs in a CentOS Stream 9/10 container.
2. **install-test** — installs the packages on the matching EL, builds the
   module against that release's `kernel-devel`, checks `modinfo` reports the
   packaged version, and smoke-tests `awg`.
3. **release** — on a tag, publishes the RPMs to a GitHub release. Debug and
   source packages stay in the run artifacts.

Only x86_64 is built. For aarch64, add a matrix entry on an `ubuntu-24.04-arm`
runner with the `-aarch64` mock config.
