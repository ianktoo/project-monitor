'use strict';

const https = require('https');
const fs = require('fs');
const path = require('path');

const pkg = require('./package.json');
const VERSION = pkg.version;

const PLATFORM_MAP = {
  'linux-x64':    'pmon-linux-x86_64',
  'darwin-arm64': 'pmon-macos-arm64',
  'win32-x64':    'pmon-windows-x86_64.exe',
};

const key = `${process.platform}-${process.arch}`;
const assetName = PLATFORM_MAP[key];

if (!assetName) {
  console.warn(
    `[pmon-cli] Unsupported platform: ${process.platform}/${process.arch}\n` +
    `  Supported: linux/x64, darwin/arm64, win32/x64\n` +
    `  Install via pip instead: pip install pmon-cli`
  );
  process.exit(0);
}

const binaryName = process.platform === 'win32' ? 'pmon.exe' : 'pmon';
const binaryPath = path.join(__dirname, 'bin', binaryName);

if (fs.existsSync(binaryPath)) {
  console.log(`[pmon-cli] Binary already present, skipping download.`);
  process.exit(0);
}

const url = `https://github.com/ianktoo/project-monitor/releases/download/v${VERSION}/${assetName}`;
console.log(`[pmon-cli] Downloading ${assetName} for v${VERSION}...`);

function download(downloadUrl, destPath, redirectsLeft, callback) {
  if (redirectsLeft <= 0) {
    return callback(new Error('Too many redirects'));
  }

  const tmpPath = destPath + '.tmp';

  https.get(downloadUrl, { headers: { 'User-Agent': 'pmon-cli-installer' } }, (res) => {
    if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
      res.resume();
      return download(res.headers.location, destPath, redirectsLeft - 1, callback);
    }

    if (res.statusCode !== 200) {
      res.resume();
      return callback(new Error(`HTTP ${res.statusCode} from ${downloadUrl}`));
    }

    fs.mkdirSync(path.dirname(destPath), { recursive: true });

    const file = fs.createWriteStream(tmpPath);
    res.pipe(file);

    file.on('finish', () => {
      file.close(() => {
        try {
          fs.renameSync(tmpPath, destPath);
          callback(null);
        } catch (err) {
          callback(err);
        }
      });
    });

    const cleanup = (err) => {
      try { fs.unlinkSync(tmpPath); } catch (_) {}
      callback(err);
    };

    file.on('error', cleanup);
    res.on('error', cleanup);
  }).on('error', callback);
}

download(url, binaryPath, 5, (err) => {
  if (err) {
    console.error(`[pmon-cli] Download failed: ${err.message}`);
    console.error(`[pmon-cli] Install via pip instead: pip install pmon-cli`);
    process.exit(0);
  }

  if (process.platform !== 'win32') {
    fs.chmodSync(binaryPath, 0o755);
  }

  console.log(`[pmon-cli] Installed to ${binaryPath}`);
});
