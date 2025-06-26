Name:      rockit-focuser-klipper
Version:   %{_version}
Release:   1%{dist}
Summary:   Daemon for controlling a multi-channel focus controller via klipper and Pyro
Url:       https://github.com/rockit-astro/focusd-klipper
License:   GPL-3.0
BuildArch: noarch

%description


%build
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_unitdir}
mkdir -p %{buildroot}/etc/bash_completion.d
mkdir -p %{buildroot}%{_sysconfdir}/focusd/

%{__install} %{_sourcedir}/focus %{buildroot}%{_bindir}
%{__install} %{_sourcedir}/klipper_focusd %{buildroot}%{_bindir}
%{__install} %{_sourcedir}/klipper_focusd@.service %{buildroot}%{_unitdir}
%{__install} %{_sourcedir}/completion/focus %{buildroot}/etc/bash_completion.d

%{__install} %{_sourcedir}/pdt.json %{buildroot}%{_sysconfdir}/focusd

%package server
Summary:  Focuser control server.
Group:    Unspecified
Requires: python3-rockit-focuser-klipper
%description server

%files server
%defattr(0755,root,root,-)
%{_bindir}/klipper_focusd
%defattr(0644,root,root,-)
%{_unitdir}/klipper_focusd@.service

%package client
Summary:  Focuser control client.
Group:    Unspecified
Requires: python3-rockit-focuser-klipper
%description client

%files client
%defattr(0755,root,root,-)
%{_bindir}/focus
/etc/bash_completion.d/focus


%package data-pdt
Summary: Data pipeline configuration for the PDT.
Group:   Unspecified
%description data-pdt

%files data-pdt
%defattr(0644,root,root,-)
%{_sysconfdir}/focusd/pdt.json

%changelog
