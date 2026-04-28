#!/usr/bin/env node
'use strict';

const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const binaryName = process.platform === 'win32' ? 'pmon.exe' : 'pmon';
const binaryPath = path.join(__dirname, binaryName);

if (!fs.existsSync(binaryPath)) {
  console.error(
    `[pmon-cli] Binary not found at: ${binaryPath}\n\n` +
    `  The postinstall step may have failed. Try:\n` +
    `    npm install -g pmon-cli\n` +
    `  Or install via pip:\n` +
    `    pip install pmon-cli`
  );
  process.exit(1);
}

const result = spawnSync(binaryPath, process.argv.slice(2), {
  stdio: 'inherit',
  shell: false,
});

if (result.error) {
  console.error(`[pmon-cli] Failed to run: ${result.error.message}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
