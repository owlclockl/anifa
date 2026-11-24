// sign.cjs — подпись APK (v1 + v2 + v3) через apk_sign_ts.
// Использование: node sign.cjs <unsigned.apk> <signed.apk> <key.pem> <cert.pem>
const { readFileSync, writeFileSync } = require('fs');
const { ApkSigner, SigningKey } = require('apk_sign_ts');

(async () => {
  const [inApk, outApk, keyPem, certPem] = process.argv.slice(2);
  const apk = new Uint8Array(readFileSync(inApk));
  const signingKey = SigningKey.fromPEM(
    readFileSync(keyPem, 'utf8'),
    readFileSync(certPem, 'utf8')
  );
  const signer = new ApkSigner({ signingKey });
  const { signedApk } = await signer.sign(apk);
  writeFileSync(outApk, Buffer.from(signedApk));
  console.log(`signed -> ${outApk} (${signedApk.length} bytes)`);
})().catch((e) => { console.error(e); process.exit(1); });
