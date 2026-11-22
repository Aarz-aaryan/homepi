# HomePi clock and kiosk

This repository preserves the Raspberry Pi framebuffer clock and companion kiosk
source. Deployment/device state is separate from this repository.

## Clock

`clock.py` displays time, weather, animated backgrounds, and resource-server
status. It requires Pillow, NumPy, requests, a configured framebuffer, fonts,
and owner-local media. Importing the clock starts hardware/network activity;
use syntax/static checks on development hosts, not an ordinary import.

The service user needs key-based SSH access and a verified known_hosts entry for
resource-server monitoring. Password authentication and embedded credentials
are deliberately not provided in published source.

## Restart helper

`restart_clock.py` uses key authentication and strict host-key checking. Set
`HOMEPI_SSH_TARGET` locally if the default alias differs. The remote account must
have narrowly scoped passwordless sudo permission for restarting the clock;
otherwise the command fails rather than asking for/storing a password.

## Security and provenance

This source update replaces historical password-bearing examples with this
credential-free guide. It does not rotate credentials or remove old Git objects.
Treat any credentials previously published in this repository as exposed and
rotate them out of band. Do not rewrite shared history without owner approval.

Local device logs, downloaded artwork, personal configuration and historical
operational notes are not automatically suitable for public publication.
No device was restarted or redeployed by this source reconciliation.
