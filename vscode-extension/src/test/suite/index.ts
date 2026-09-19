import { readdir } from 'node:fs/promises';
import * as path from 'node:path';
import Mocha from 'mocha';

export async function run(): Promise<void> {
  const testRoot = __dirname;
  const entries = await readdir(testRoot, { withFileTypes: true });
  const files = entries
    .filter(entry => entry.isFile() && entry.name.endsWith('.test.js'))
    .map(entry => path.join(entry.parentPath, entry.name));
  const runner = new Mocha({
    ui: 'tdd',
    color: true,
    timeout: 10000,
  });
  for (const file of files) {
    runner.addFile(file);
  }

  const failures = await new Promise<number>(resolve => {
    runner.run((failed: number) => resolve(failed));
  });
  if (failures > 0) {
    throw new Error(`${failures} extension test(s) failed`);
  }
}
