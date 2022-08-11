#!/usr/bin/env node
/*
 * ES6 REPL Emulator
 * -----------------
 *
 * See https://nodejs.org/api/repl.html#repl_repl_start_options
 * for additional configuration options.
 *
*/

var repl = require('babel-node');


// This has VI bindings already!
var config = {
  prompt: "es6>> ",
  useColor: true,
}


repl.start(prompt);
