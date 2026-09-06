Name:           amneziawg-tools
Version:        3.1.20260812
Release:        1%{?dist}
Summary:        Userspace tools for AmneziaWG (awg, awg-quick)

License:        GPL-2.0-only
URL:            https://github.com/amnezia-vpn/amneziawg-tools
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  systemd-rpm-macros

# Ships unit files but has no scriptlets to run: template units and a target
# need neither enabling nor a daemon-reload on install.
%{?systemd_requires}

# awg-quick(8) is a bash script driving `ip`; bash itself comes in through the
# shebang's auto-generated dependency.
Requires:       iproute
# Weak: the kernel module is the usual backend, but awg-quick also runs on a
# userspace implementation (WG_QUICK_USERSPACE_IMPLEMENTATION, amneziawg-go).
Recommends:     amneziawg-dkms

%description
Userspace side of AmneziaWG, a WireGuard fork that obfuscates handshakes and
packet headers against DPI. This is the upstream wireguard-tools tree with
every command renamed: awg instead of wg, awg-quick instead of wg-quick,
awg-quick@.service instead of wg-quick@.service, and /etc/amnezia/amneziawg
instead of /etc/wireguard — so it installs alongside wireguard-tools without
conflicting.

%prep
%autosetup -p1

%build
%set_build_flags
%make_build -C src RUNSTATEDIR=%{_rundir}

%install
%make_install -C src \
    BINDIR=%{_bindir} \
    MANDIR=%{_mandir} \
    SYSCONFDIR=%{_sysconfdir} \
    BASHCOMPDIR=%{_datadir}/bash-completion/completions \
    SYSTEMDUNITDIR=%{_unitdir} \
    RUNSTATEDIR=%{_rundir} \
    WITH_BASHCOMPLETION=yes WITH_WGQUICK=yes WITH_SYSTEMDUNITS=yes

%files
%license COPYING
%doc README.md
%{_bindir}/awg
%{_bindir}/awg-quick
# The Makefile creates the config dir 0700 and leaves the parent at the
# umask's mercy; %%attr pins both, since the private keys land in there.
%dir %attr(0755,root,root) %{_sysconfdir}/amnezia
%dir %attr(0700,root,root) %{_sysconfdir}/amnezia/amneziawg
%{_datadir}/bash-completion/completions/awg
%{_datadir}/bash-completion/completions/awg-quick
%{_unitdir}/awg-quick@.service
%{_unitdir}/awg-quick.target
%{_mandir}/man8/awg.8*
%{_mandir}/man8/awg-quick.8*

%changelog
* Sun Sep 06 2026 blennuria <blennuria@pm.me> - 3.1.20260812-1
- Initial package
