#!/usr/bin/env node
"use strict";

const { main } = require("./lib");

main(process.argv.slice(2))
  .then((result) => {
    if (result.stdout) process.stdout.write(result.stdout);
    if (result.stderr) process.stderr.write(result.stderr);
    process.exit(result.code);
  })
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
