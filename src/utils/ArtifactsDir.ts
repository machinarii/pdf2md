import { existsSync } from 'node:fs';
import path from 'node:path';
import { DEFAULT_ARTIFACTS_DIR, ENV_VARS } from '@/constants';

let cached: string | null = null;

/**
 * Resolve the `book-artifacts/` directory to an absolute path that doesn't
 * depend on the process CWD. Resolution order:
 *
 *   1. `CONFIG_DIR` environment variable (resolved to absolute)
 *   2. `<package-root>/book-artifacts` — where package-root is the nearest
 *      ancestor of this module that contains a `package.json`. This keeps
 *      the CLI usable from any CWD when installed globally via `npm link`.
 *   3. `<CWD>/book-artifacts` — legacy behavior when package root can't be
 *      determined.
 */
export function getArtifactsDir(): string {
    if (cached) return cached;

    const fromEnv = process.env[ENV_VARS.CONFIG_DIR];
    if (fromEnv) {
        cached = path.resolve(fromEnv);
        return cached;
    }

    const packageRoot = findPackageRoot(__dirname);
    cached = packageRoot
        ? path.join(packageRoot, DEFAULT_ARTIFACTS_DIR)
        : path.resolve(DEFAULT_ARTIFACTS_DIR);
    return cached;
}

function findPackageRoot(startDir: string): string | null {
    let current = startDir;
    for (let i = 0; i < 10; i++) {
        if (existsSync(path.join(current, 'package.json'))) return current;
        const parent = path.dirname(current);
        if (parent === current) return null;
        current = parent;
    }
    return null;
}

/** Reset the cache — only used by tests. */
export function resetArtifactsDirCache(): void {
    cached = null;
}
