"""
CuPy GPU fix for Windows with special characters (emoji/CJK) in username path.

Apply this module before using CuPy JIT features (ElementwiseKernel, fused ops, etc.)

Usage:
    from cupy_gpu_fix import apply_fix
    apply_fix()
    import cupy as cp  # now JIT works

The fix:
1. Sets TMP/TEMP/CUPY_CACHE_DIR to ASCII-only paths
2. Copies CuPy + CCCL + CUDA runtime headers to C:/cupy_include/
3. Monkey-patches NVRTC to use the clean include path
"""
import os, sys, shutil

_CLEAN_INCLUDE = 'C:/cupy_include'
_FIX_APPLIED = False


def _setup_clean_headers():
    """Copy all needed headers to ASCII-only path (one-time)."""
    global _CLEAN_INCLUDE

    if os.path.isdir(_CLEAN_INCLUDE):
        # Already set up — just verify it has files
        for _ in os.listdir(_CLEAN_INCLUDE):
            return _CLEAN_INCLUDE  # non-empty, assume valid
        # Empty — rebuild
        shutil.rmtree(_CLEAN_INCLUDE)

    os.makedirs(_CLEAN_INCLUDE, exist_ok=True)

    import cupy as cp
    cupy_dir = os.path.dirname(cp.__file__)

    # CuPy headers
    src_cupy = os.path.join(cupy_dir, '_core', 'include')
    if os.path.isdir(src_cupy):
        shutil.copytree(src_cupy, _CLEAN_INCLUDE, dirs_exist_ok=True)

    nvidia_dir = os.path.expandvars(r'%APPDATA%\Python\Python313\site-packages\nvidia')

    # CCCL headers (thrust, cub, cuda, nv)
    src_cccl = os.path.join(nvidia_dir, 'cuda_cccl', 'include')
    if os.path.isdir(src_cccl):
        for sub in ['thrust', 'cub', 'cuda', 'nv']:
            src_sub = os.path.join(src_cccl, sub)
            dst_sub = os.path.join(_CLEAN_INCLUDE, sub)
            if os.path.isdir(src_sub):
                shutil.copytree(src_sub, dst_sub, dirs_exist_ok=True)

    # CUDA runtime headers
    src_crt = os.path.join(nvidia_dir, 'cuda_runtime', 'include')
    if os.path.isdir(src_crt):
        for f in os.listdir(src_crt):
            sf = os.path.join(src_crt, f)
            df = os.path.join(_CLEAN_INCLUDE, f)
            if os.path.isfile(sf) and not os.path.exists(df):
                shutil.copy2(sf, df)
        cg_src = os.path.join(src_crt, 'cooperative_groups')
        cg_dst = os.path.join(_CLEAN_INCLUDE, 'cooperative_groups')
        if os.path.isdir(cg_src):
            shutil.copytree(cg_src, cg_dst, dirs_exist_ok=True)

    return _CLEAN_INCLUDE


def apply_fix():
    """Apply the CuPy JIT fix. Idempotent — safe to call multiple times."""
    global _FIX_APPLIED
    if _FIX_APPLIED:
        return

    # Ensure env vars
    env_vars = {
        'TMP': 'C:/temp',
        'TEMP': 'C:/temp',
        'CUPY_CACHE_DIR': 'C:/cupy_cache',
        'CUDA_PATH': os.path.expandvars(
            r'%APPDATA%\Python\Python313\site-packages\nvidia'),
    }
    for k, v in env_vars.items():
        os.environ[k] = v

    # Ensure cache dirs exist
    for d in ['C:/temp', 'C:/cupy_cache']:
        os.makedirs(d, exist_ok=True)

    # Setup clean headers (one-time copy)
    clean_inc = _setup_clean_headers()

    # Monkey-patch CuPy compiler
    from cupy.cuda import compiler
    _original_get_opts = compiler._get_extra_include_dir_opts

    def _patched_get_extra_include_dir_opts():
        opts = _original_get_opts()
        return opts + (f'-I{clean_inc}',)

    compiler._get_extra_include_dir_opts = _patched_get_extra_include_dir_opts

    _FIX_APPLIED = True
