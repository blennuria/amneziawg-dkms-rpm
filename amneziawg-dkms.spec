%global module   amneziawg
%global upstream amneziawg-linux-kernel-module

Name:           amneziawg-dkms
Version:        3.1.20260906
Release:        1%{?dist}
# The upstream COPR (amneziavpn/amneziawg) publishes 1:1.0.20241112 and has
# been dormant since. Without an epoch of our own that stale package outranks
# everything we build here, so keep the epoch and stay upgradable from it.
Epoch:          1
Summary:        AmneziaWG kernel module (DKMS)

License:        GPL-2.0-only
URL:            https://github.com/amnezia-vpn/amneziawg-linux-kernel-module
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{upstream}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  make

Requires:       dkms >= 2.2.0
Requires:       gcc
Requires:       make
Requires(posttrans): dkms >= 2.2.0
Requires(preun):     dkms >= 2.2.0
# Weak on purpose: kernel-devel resolves to the newest kernel in the repos,
# which is not necessarily the one that is running. Same for libelf, which
# only some kernel trees need to relink their host tools.
Recommends:     kernel-devel
Recommends:     elfutils-libelf-devel
Recommends:     amneziawg-tools

Provides:       kmod(amneziawg.ko) = %{epoch}:%{version}-%{release}
Conflicts:      kmod-%{module}

%description
AmneziaWG is a fork of WireGuard that disguises the handshake and the packet
headers (junk packets, header obfuscation, magic headers) so that DPI cannot
fingerprint the protocol. This package ships the kernel module sources and
registers them with DKMS, so the module is rebuilt automatically on every
kernel update.

The interface type provided by the module is `amneziawg`; the userspace side
(awg, awg-quick) lives in the amneziawg-tools package.

On EL10 and any other distribution where the `dkms` package ships
/etc/dkms/sign_helper.sh, the built module is signed with a MOK key generated
under /var/lib/dkms/. The %%posttrans scriptlet prints how to enrol that key
with mokutil so the module can load under Secure Boot.

%prep
%autosetup -n %{upstream}-%{version}

# Upstream leaves a placeholder version in three places. DKMS reads dkms.conf,
# kbuild reads version.h (the Makefile value only reaches the compiler on a
# manual `make`, not on the `make -C $kdir M=$builddir` DKMS runs by default),
# so all three have to name the packaged version — otherwise `modinfo
# amneziawg` reports a version nobody can map back to an RPM.
sed -i 's/^PACKAGE_VERSION=.*/PACKAGE_VERSION="%{version}"/'        src/dkms.conf
sed -i 's/^WIREGUARD_VERSION = .*/WIREGUARD_VERSION = %{version}/'  src/Makefile
sed -i 's/^#define WIREGUARD_VERSION .*/#define WIREGUARD_VERSION "%{version}"/' src/version.h

%build
# Nothing to compile at package time: DKMS builds the module on the target.

%install
make -C src dkms-install \
    DESTDIR=%{buildroot} \
    DKMSDIR=%{_usrsrc}/%{module}-%{version}

%files
%license COPYING
%doc README.md
%{_usrsrc}/%{module}-%{version}/

# Everything runs from %%posttrans, not %%post: building the module before the
# rest of the transaction has settled can race with a kernel upgrade in the
# same transaction and build against a half-installed kernel. Running last also
# repairs the same-version upgrade case, where the outgoing package's %%preun
# removes the DKMS tree the incoming one just registered.
%posttrans
dkms add -m %{module} -v %{version} >/dev/null 2>&1 || :
# `dkms install`, not `dkms autoinstall`: autoinstall ignores -m/-v and would
# rebuild every DKMS module on the box during our transaction. install builds
# first when needed, so this is a build + install for the running kernel. The
# no-autoinstall flag is dkms' opt-out from exactly this, so honour it.
if [ ! -e /etc/dkms/no-autoinstall ] \
   && ! dkms install -m %{module} -v %{version} >/dev/null 2>&1; then
    echo "[amneziawg-dkms] dkms install failed (kernel-devel for the running kernel missing?); check 'dkms status' and /var/lib/dkms/%{module}/%{version}/build/make.log" >&2
fi

# Under Secure Boot the auto-signed module won't load unless the MOK public
# key is enrolled. Stay silent on machines that don't need it.
if [ -s /var/lib/dkms/mok.pub ] \
   && command -v mokutil >/dev/null 2>&1 \
   && mokutil --sb-state 2>/dev/null | grep -qi enabled; then
    if ! mokutil --test-key /var/lib/dkms/mok.pub >/dev/null 2>&1; then
        cat >&2 <<'EOM'
[amneziawg-dkms] amneziawg.ko was signed with the DKMS MOK key at
[amneziawg-dkms]     /var/lib/dkms/mok.pub
[amneziawg-dkms] Under Secure Boot, enrol it once with:
[amneziawg-dkms]     sudo mokutil --import /var/lib/dkms/mok.pub
[amneziawg-dkms] then reboot and accept the prompt in MokManager.
EOM
    fi
fi

# Unconditional, not guarded on $1 == 0: on an upgrade to a different version
# this removes the version being replaced (whose /usr/src tree rpm is about to
# delete), while the incoming one has its own version string and is untouched.
%preun
dkms remove -m %{module} -v %{version} --all >/dev/null 2>&1 || :

%changelog
* Sun Sep 06 2026 blennuria <blennuria@pm.me> - 1:3.1.20260906-1
- Initial package
