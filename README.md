# amneziawg-dkms-rpm

RPM packaging of the [AmneziaWG kernel
module](https://github.com/amnezia-vpn/amneziawg-linux-kernel-module) for EL9
and EL10, built in GitHub Actions with mock. Produces one noarch package,
`amneziawg-dkms`, which ships the module sources and lets DKMS rebuild them on
every kernel update.

The userspace side — `awg`, `awg-quick` — is packaged separately in
[amneziawg-tools-rpm](https://github.com/blennuria/amneziawg-tools-rpm); the two
upstreams have their own version streams, which is why they are not packaged
together.

The upstream COPR (`amneziavpn/amneziawg`) has been stuck on 1.0.20241112 since
November 2024, which is the 1.x module. This tracks the 3.x branch and keeps
that COPR's `Epoch: 1`, so it upgrades cleanly over a package installed
from there.

## Install

```shell
# dkms lives in EPEL and drags in gcc, make and the kernel-devel matching the
# running kernel
sudo dnf install -y epel-release
sudo dnf install -y https://github.com/blennuria/amneziawg-dkms-rpm/releases/latest/download/amneziawg-dkms-3.1.20260906-1.el9.noarch.rpm
```

`%posttrans` runs `dkms install` for the running kernel and honours
`/etc/dkms/no-autoinstall`. If the machine has no `kernel-devel` matching the
running kernel (typical right after a kernel update, before the reboot), the
build is skipped with a warning; `dkms status` shows where things stand and
`/var/lib/dkms/amneziawg/<version>/build/make.log` says why a build failed.

Both EL9 (5.14) and EL10 (6.12) kernels ship `CONFIG_WIREGUARD=m` and the crypto
library modules the module links against, so nothing else is needed. The module
registers `rtnl-link-amneziawg`, so `ip link add … type amneziawg` and
`awg-quick` load it on demand.

### Secure Boot

EPEL's dkms signs the module with a MOK key it generates under
`/var/lib/dkms/`. Enrol it once:

```shell
sudo mokutil --import /var/lib/dkms/mok.pub
```

then reboot and accept the prompt in MokManager. The `%posttrans` scriptlet
prints this only when Secure Boot is on and the key is not enrolled yet.

## Patches

`0001-compat-probe-the-headers-for-backported-apis.patch` is the only local
change, and without it the module compiles on neither target. Upstream's compat
layer picks its shims from `LINUX_VERSION_CODE` alone, while EL kernels backport
APIs without moving that number:

- Stream 9 (5.14.0-741) has `timer_container_of` and no longer has
  `from_timer`, so every timer callback fails with
  `implicit declaration of function 'from_timer'`;
- Stream 10 (6.12.0-264) has `struct sockaddr_inet`, `netif_threaded_enable`
  and `struct rtnl_newlink_params`, each of which the compat layer defines a
  second time.

The patch turns those four into header probes in `compat/Kbuild.include`, next
to the ones already there for ptr_ring, siphash and dst_cache, so no version
numbers have to be kept up to date. Upstream PR
[#174](https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/pull/174)
fixes part of the same breakage for RHEL 10 by enumerating minor releases; drop
this patch if that or an equivalent lands upstream.

## Updating

Bump `Version:`, add a `%changelog` entry, push a tag. Nothing else references
the version — the workflow takes the source URL out of the spec.

Tags are `<version>-<release>` (e.g. `3.1.20260906-1`), and the build refuses to
publish when the tag and the spec disagree.

Upstream releases the module more often than the tools — they share a tag date
only on joint release days — so the two packages are normally on different
versions, which is fine as long as they agree on the netlink API. When bumping,
check that the tools can still configure everything the module exposes:

```shell
kmod=3.1.20260906; tools=3.1.20260812
attrs() { grep -oE 'WG(DEVICE|PEER)_A_[A-Z0-9_]+' - \
          | sed 's/^WGPEER_A_AWG$/WGPEER_A_ADVANCED_SECURITY/' | sort -u; }
diff <(curl -fsSL https://raw.githubusercontent.com/amnezia-vpn/amneziawg-linux-kernel-module/v$kmod/src/uapi/wireguard.h | attrs) \
     <(curl -fsSL https://raw.githubusercontent.com/amnezia-vpn/amneziawg-tools/v$tools/src/uapi/linux/linux/wireguard.h | attrs)
```

Empty output means the packaged pair is interchangeable with a joint upstream
release. (The two repos spell attribute 11 differently —
`WGPEER_A_ADVANCED_SECURITY` versus `WGPEER_A_AWG` — for the same value, hence
the `sed`.)

## Testing locally

The CI jobs are reproducible in a container — `podman`, `docker` or Apple's
`container`, with `--arch amd64` where the host is not x86_64:

```shell
container run --rm --arch amd64 -v "$PWD":/work quay.io/centos/centos:stream9 bash -c '
  dnf install -y --nogpgcheck epel-release
  dnf install -y --nogpgcheck --enablerepo=crb rpm-build rpmdevtools gcc make \
      dkms kernel-devel elfutils-libelf-devel
  rpmdev-setuptree && cp /work/*.spec ~/rpmbuild/SPECS/ && cp /work/*.patch ~/rpmbuild/SOURCES/
  spectool -g -C ~/rpmbuild/SOURCES ~/rpmbuild/SPECS/amneziawg-dkms.spec
  rpmbuild -ba ~/rpmbuild/SPECS/amneziawg-dkms.spec
  dnf install -y ~/rpmbuild/RPMS/noarch/*.rpm
  k=$(rpm -q kernel-devel --qf "%{VERSION}-%{RELEASE}.%{ARCH}")
  ln -sfn /usr/src/kernels/$k /lib/modules/$k/build 2>/dev/null || true
  dkms install -m amneziawg -v $(rpm -q --qf %{VERSION} amneziawg-dkms) -k $k'
```

In a container `%posttrans` cannot build for you, because `uname -r` is the
host's kernel — hence the explicit `dkms install -k`.

## CI

`.github/workflows/build.yml`:

1. **build** — mock builds SRPM + RPM in a CentOS Stream 9/10 container.
2. **install-test** — installs the package on the matching EL, builds the module
   against that release's `kernel-devel`, and checks that `modinfo` reports the
   packaged version and the rtnl alias, then that erasing the package leaves no
   DKMS state behind.
3. **release** — on a tag, publishes the RPMs to a GitHub release.

Only x86_64 is built. For aarch64, add a matrix entry on an `ubuntu-24.04-arm`
runner with the `-aarch64` mock config.
