# Company CA certificate setup (Windows)

Requests does not automatically use every certificate installed in the Windows certificate store.
For the application, give Requests a CA bundle file explicitly.

## Recommended

1. Ask IT/Security for the corporate Root CA and any required Intermediate CA certificates.
2. Export them in Base-64 X.509 / PEM format.
3. If there are multiple certificates, concatenate them into one file, for example:

   `C:\certs\company-ca-bundle.pem`

4. In `run_spyder_internal.py`, set:

```python
CA_BUNDLE = r"C:\certs\company-ca-bundle.pem"
```

5. Keep:

```python
verify_ssl=True
```

This keeps TLS certificate verification enabled.

## If your company gave you a `.cer` file

Open it with Windows and check whether it is Base-64 / PEM or DER encoded.
If it is Base-64, Requests can often use it directly. If it is binary DER, convert/export it
to Base-64 X.509 / PEM or obtain the PEM version from IT.

## Temporary diagnostic only

```python
verify_ssl=False
```

This can confirm that the only blocker is certificate trust, but it should not be used in the final application.

## Alternative: environment variable

You can also set:

```powershell
$env:REQUESTS_CA_BUNDLE = "C:\certs\company-ca-bundle.pem"
```

Then `requests` will use that CA bundle for the process.
