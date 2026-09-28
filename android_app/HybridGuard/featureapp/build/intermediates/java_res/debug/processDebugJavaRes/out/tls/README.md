# Legacy Android collection TLS root

`isrg_root_x1.pem` is the public, self-signed ISRG Root X1 certificate downloaded
from https://letsencrypt.org/certs/isrgrootx1.pem on 2026-09-18. It expires on
2035-06-04. Official certificate information: https://letsencrypt.org/certificates/.

`CollectionTls` adds this root to the collection HTTP clients on API 21–25 only,
alongside normal system trust. Android 7.1.0 shares API 25 with 7.1.1, so the
whole API level is covered. Certificate chain, validity and hostname checks
remain enabled. There is no HTTP downgrade and no global trust override.

This does not update the OS trust store or an external browser. Both the probe
page and the browser upload API still require a server certificate chain that
the selected browser trusts. See `deployment/legacy-android/README.md` at the
repository root for the pending deployment work.
