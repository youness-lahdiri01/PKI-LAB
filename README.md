# mini-pki-lab

A hands-on lab demonstrating a complete PKI lifecycle: **Root CA → Intermediate CA → server/client certificates**, mutual TLS authentication, certificate **revocation with CRL**, and renewal.

## Hierarchy

```
MiniPKI Root CA (self-signed, 10 years)
└── MiniPKI Intermediate CA (5 years, pathlen:0)
    ├── server certificate  (serverAuth, SAN: localhost / 127.0.0.1)
    └── client certificate  (clientAuth)
```

## Layout

```
mini-ca/
├── intermediate.cnf      # OpenSSL CA config (signing policy, CRL settings)
├── intermediate.ext      # Extensions for the intermediate CA certificate
├── server.ext            # Extensions for server certificates
├── client.ext            # Extensions for client certificates
├── server.py             # mTLS demo server (Python, port 8443, CERT_REQUIRED)
├── private/              # private keys — generated locally, never committed
├── certs/                # issued certificates — generated locally
├── csr/                  # certificate signing requests — generated locally
└── crl/                  # certificate revocation lists — generated locally
```

> **Note:** `private/`, `certs/`, `csr/` and `crl/` are git-ignored. Clone the repo and run the setup below to generate everything locally.

## Quick start

### 1. Root CA — self-signed, 10 years

```bash
cd mini-ca
mkdir -p private certs csr crl newcerts
touch index.txt && echo 1000 > serial && echo 1000 > crlnumber

openssl genrsa -out private/ca.key.pem 4096
openssl req -x509 -new -nodes -key private/ca.key.pem -sha256 -days 3650 \
  -subj "/CN=MiniPKI Root CA/O=MiniPKI Lab" -out certs/ca.cert.pem
```

### 2. Intermediate CA — signed by the Root, 5 years

```bash
openssl genrsa -out private/intermediate.key.pem 4096
openssl req -new -key private/intermediate.key.pem \
  -subj "/CN=MiniPKI Intermediate CA/O=MiniPKI Lab" -out csr/intermediate.csr.pem
openssl x509 -req -in csr/intermediate.csr.pem -CA certs/ca.cert.pem \
  -CAkey private/ca.key.pem -CAcreateserial -days 1825 -sha256 \
  -extfile intermediate.ext -out certs/intermediate.cert.pem
```

### 3. Issue server and client certificates (signed by the Intermediate)

```bash
# Server
openssl genrsa -out private/server.key.pem 2048
openssl req -new -key private/server.key.pem -subj "/CN=localhost" -out csr/server.csr.pem
openssl ca -config intermediate.cnf -extensions server_cert -days 825 -notext \
  -in csr/server.csr.pem -out certs/server.cert.pem
cat certs/server.cert.pem certs/intermediate.cert.pem > certs/server-chain.pem

# Client
openssl genrsa -out private/client.key.pem 2048
openssl req -new -key private/client.key.pem -subj "/CN=lab-client" -out csr/client.csr.pem
openssl ca -config intermediate.cnf -extensions client_cert -days 825 -notext \
  -in csr/client.csr.pem -out certs/client.cert.pem
cat certs/client.cert.pem certs/intermediate.cert.pem > certs/client-chain.pem
```

### 4. Run the mTLS server

```bash
python3 server.py
# mTLS server listening on https://127.0.0.1:8443
```

The server requires a client certificate (`ssl.CERT_REQUIRED`) chained to the Root CA.

### 5. Test — with and without a client certificate

```bash
# With a valid client certificate → 200 OK
curl --cacert certs/ca.cert.pem \
  --cert certs/client-chain.pem --key private/client.key.pem \
  https://127.0.0.1:8443/
# → mTLS OK: client certificate verified!

# Without a client certificate → TLS handshake failure
curl --cacert certs/ca.cert.pem https://127.0.0.1:8443/
# → curl: (35) error:0A00045B:SSL routines::tlsv13 alert certificate required
```

### 6. Revocation — revoke the client cert and publish the CRL

```bash
openssl ca -config intermediate.cnf -revoke certs/client.cert.pem
openssl ca -config intermediate.cnf -gencrl -out crl/intermediate.crl.pem

# Before revocation: OK — after revocation: verification fails
openssl verify -CAfile certs/ca.cert.pem -untrusted certs/intermediate.cert.pem \
  -crl_check -CRLfile crl/intermediate.crl.pem certs/client.cert.pem
# → error 23 at 0 depth lookup: certificate revoked
```

## Key takeaways

- A two-tier CA hierarchy limits exposure: the Root key signs once (the Intermediate) and goes offline; day-to-day issuance happens at the Intermediate level with `pathlen:0`.
- `keyUsage` / `extendedKeyUsage` extensions constrain what each certificate can do — the server cert cannot sign other certs, the client cert is authentication-only.
- mTLS shifts trust from passwords to cryptographic identity: the server rejects any client that cannot present a chain to the trusted Root.
- Revocation is a distribution problem as much as a crypto one — the CRL must reach every verifier, which is why short-lived certificates are increasingly preferred in production.
