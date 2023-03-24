#!/bin/bash

# WIP test for validating Windows tools built in AOSP.
#
# Steps to run this test
# 1. Install Wine: sudo apt install wine64
#
# 2. Build AOSP Windows modules.  In an AOSP tree, run:
#   m native-host-cross
#
# 3. Run the test:
#   sh <path-to-llvm-toolchain>/toolchain/llvm_android/test/platform/run_windows_tests.sh
# This copies 32-bit libraries to $PWD/windows-test-dir/32 and 64-bit
# libraries to $PWD/windows-test-dir/64 and runs the tests.
#
# 4. Validate: Output of gtests is stored in windows-test-dir/*/*.txt.
# Validate known failures.
#   grep "listed below" windows-test-dir/*/*.txt | sed "s/32\// /g" | \
#     sed "s/64\// /g" | sort -k 2
# See go/android-llvm-windows-testing for the current list of failing tests.


panic ()
{
    1>&2 echo "Error: $@"
    exit 1
}

fail_panic ()
{
    if [ $? != 0 ]; then
        panic "$@"
    fi
}

fail_panic_exit_code ()
{
    local exit_code=$?
    if [ $exit_code != $1 ]; then
        1>&2 echo Expected exit code: $1.  Got $exit_code
        panic "$2"
    fi
}

TMP_DIR=./windows-test-dir
TMP_DIR_32=$TMP_DIR/32
TMP_DIR_64=$TMP_DIR/64

clean_tmp_dirs() {
  rm -rf $TMP_DIR
}

make_tmp_dirs() {
  clean_tmp_dirs

  mkdir -p $TMP_DIR_32
  mkdir -p $TMP_DIR_64
}

copy_dlls() {
  local dlls_32=(
    prebuilts/gcc/linux-x86/host/x86_64-w64-mingw32-4.8/x86_64-w64-mingw32/lib32/libwinpthread-1.dll
    out/soong/.intermediates/system/libbase/libbase/windows_x86_shared/libbase.dll
    out/host/windows-x86/obj/SHARED_LIBRARIES/AdbWinApi_intermediates/AdbWinApi.dll
    out/soong/.intermediates/external/clang/libclang_android/windows_x86_shared/libclang_android.dll
    out/soong/.intermediates/external/llvm/libLLVM_android/windows_x86_shared/libLLVM_android.dll
    out/soong/.intermediates/frameworks/compile/libbcc/lib/libbcc/windows_x86_shared/libbcc.dll
    out/soong/.intermediates/frameworks/compile/libbcc/bcinfo/libbcinfo/windows_x86_shared/libbcinfo.dll
    out/soong/.intermediates/system/logging/liblog/liblog/windows_x86_shared/liblog.dll

    out/host/windows-x86/obj/SHARED_LIBRARIES/libziparchive_intermediates/libziparchive.dll
    out/host/windows-x86/obj/SHARED_LIBRARIES/liblzma_intermediates/liblzma.dll
    out/host/windows-x86/obj/SHARED_LIBRARIES/libprotobuf-cpp-lite_intermediates/libprotobuf-cpp-lite.dll
    out/soong/.intermediates/external/zlib/libz/windows_x86_shared/libz-host.dll
  )
  local dlls_64=(
    prebuilts/gcc/linux-x86/host/x86_64-w64-mingw32-4.8/x86_64-w64-mingw32/bin/libwinpthread-1.dll
    out/soong/.intermediates/system/libbase/libbase/windows_x86_64_shared/libbase.dll
    out/soong/.intermediates/system/logging/liblog/liblog/windows_x86_64_shared/liblog.dll

    out/host/windows-x86/obj64/SHARED_LIBRARIES/libziparchive_intermediates/libziparchive.dll
    out/host/windows-x86/obj64/SHARED_LIBRARIES/liblzma_intermediates/liblzma.dll
    out/host/windows-x86/obj64/SHARED_LIBRARIES/libprotobuf-cpp-lite_intermediates/libprotobuf-cpp-lite.dll
    out/soong/.intermediates/external/zlib/libz/windows_x86_64_shared/libz-host.dll
  )

  for index in "${!dlls_32[@]}"
  do
    local dll=${dlls_32[index]}
    cp $dll $TMP_DIR_32
    fail_panic "Failed to copy " $dll
  done

  for index in "${!dlls_64[@]}"
  do
    local dll=${dlls_64[index]}
    cp $dll $TMP_DIR_64
    fail_panic "Failed to copy " $dll
  done

  cp -rf system/libziparchive/testdata $TMP_DIR_32
  cp -rf system/libziparchive/testdata $TMP_DIR_64
}

run_smoke_tests() {
  # TODO Check if we add more executables
  local exes_32=(
    "out/soong/.intermediates/frameworks/base/tools/aapt2/aapt2/windows_x86/aapt2.exe;1"
    "out/soong/.intermediates/frameworks/base/tools/aapt2/aapt2_tests/windows_x86/aapt2_tests.exe;0"
    "out/soong/.intermediates/frameworks/base/tools/aapt/aapt/windows_x86/aapt.exe;2"
    # http://b/145154677 - adb is not using wmain and fails with an error.
    # "out/soong/.intermediates/system/core/adb/adb/windows_x86/adb.exe;0"
    # "out/soong/.intermediates/system/core/adb/adb_test/windows_x86/adb_test.exe;0"
    "out/soong/.intermediates/system/tools/aidl/aidl-cpp/windows_x86/aidl-cpp.exe;0"
    "out/soong/.intermediates/system/tools/aidl/aidl/windows_x86/aidl.exe;0"
    "out/soong/.intermediates/external/protobuf/aprotoc/windows_x86/aprotoc.exe;0"
    "out/soong/.intermediates/frameworks/compile/libbcc/tools/bcc_compat/bcc_compat/windows_x86/bcc_compat.exe;0"
    "out/soong/.intermediates/build/soong/cc/libbuildversion/tests/build_version_test/windows_x86/build_version_test.exe;0"
    "out/soong/.intermediates/art/dexdump/dexdump/windows_x86/dexdump.exe;2"
    "out/soong/.intermediates/art/tools/dmtracedump/dmtracedump/windows_x86/dmtracedump.exe;2"
    "out/soong/.intermediates/development/tools/etc1tool/etc1tool/windows_x86/etc1tool.exe;1"
    "out/soong/.intermediates/system/core/fastboot/fastboot/windows_x86/fastboot.exe;0"
    "out/soong/.intermediates/system/core/fastboot/fastboot_test/windows_x86/fastboot_test.exe;0"
    "out/soong/.intermediates/dalvik/tools/hprof-conv/hprof-conv/windows_x86/hprof-conv.exe;2"
    "out/soong/.intermediates/art/tools/jfuzz/jfuzz/windows_x86/jfuzz.exe;1"
    "out/soong/.intermediates/frameworks/base/tools/aapt/libaapt_tests/windows_x86/libaapt_tests.exe;0"
    "out/soong/.intermediates/system/libbase/libbase_test/windows_x86/libbase_test32.exe;0"
    "out/soong/.intermediates/frameworks/base/tools/split-select/libsplit-select_tests/windows_x86/libsplit-select_tests.exe;0"
    "out/soong/.intermediates/frameworks/compile/slang/llvm-rs-as/windows_x86/llvm-rs-as.exe;0"
    "out/soong/.intermediates/frameworks/compile/slang/llvm-rs-cc/windows_x86/llvm-rs-cc.exe;0"
    "out/soong/.intermediates/external/f2fs-tools/make_f2fs/windows_x86/make_f2fs.exe;1"
    "out/soong/.intermediates/external/mdnsresponder/mdnsd/windows_x86/mdnsd.exe;0"
    "out/soong/.intermediates/external/e2fsprogs/misc/mke2fs/windows_x86/mke2fs.exe;1"
    "out/host/windows-x86/obj/EXECUTABLES/simpleperf_ndk_intermediates/simpleperf_ndk.exe;0"
    "out/host/windows-x86/obj/NATIVE_TESTS/simpleperf_unit_test_intermediates/simpleperf_unit_test.exe;1"
    "out/soong/.intermediates/frameworks/base/tools/split-select/split-select/windows_x86/split-select.exe;0"
    "out/soong/.intermediates/external/sqlite/dist/sqlite3/windows_x86/sqlite3.exe;1"
    "out/soong/.intermediates/build/make/tools/zipalign/zipalign/windows_x86/zipalign.exe;2"
    "out/soong/.intermediates/system/libziparchive/ziparchive-tests/windows_x86/ziparchive-tests.exe;0"
    "out/soong/.intermediates/build/make/tools/ziptime/ziptime/windows_x86/ziptime.exe;1"
  )

  local exes_64=(
    "out/soong/.intermediates/frameworks/base/tools/aapt2/aapt2_tests/windows_x86_64/aapt2_tests.exe;0"
    "out/soong/.intermediates/system/libziparchive/ziparchive-tests/windows_x86_64/ziparchive-tests.exe;0"
    "out/soong/.intermediates/frameworks/base/tools/split-select/libsplit-select_tests/windows_x86_64/libsplit-select_tests.exe;0"
    "out/soong/.intermediates/system/libbase/libbase_test/windows_x86_64/libbase_test64.exe;0"
    "out/soong/.intermediates/frameworks/base/tools/aapt/libaapt_tests/windows_x86_64/libaapt_tests.exe;0"
    "out/soong/.intermediates/build/soong/cc/libbuildversion/tests/build_version_test/windows_x86_64/build_version_test.exe;0"
    "out/host/windows-x86/obj64/EXECUTABLES/simpleperf_ndk_intermediates/simpleperf_ndk64.exe;0"
    "out/host/windows-x86/obj64/NATIVE_TESTS/simpleperf_unit_test_intermediates/simpleperf_unit_test.exe;1"
  )

  for index in "${!exes_32[@]}"
  do
    local entry=${exes_32[index]}
    local split=(${entry//;/ })
    local exe=${split[0]}
    local exit_code=${split[1]}
    Path=$TMP_DIR_32 wine $exe --help 2>/dev/null > /dev/null
    fail_panic_exit_code $exit_code $exe
  done

  for index in "${!exes_64[@]}"
  do
    local entry=${exes_64[index]}
    local split=(${entry//;/ })
    local exe=${split[0]}
    local exit_code=${split[1]}
    Path=$TMP_DIR_64 wine $exe --help 2>/dev/null > /dev/null
    fail_panic_exit_code $exit_code $exe
  done
}

run_gtests() {
  # TODO Check if we add more executables
  local exes_32=(
    "out/soong/.intermediates/frameworks/base/tools/aapt2/aapt2_tests/windows_x86/aapt2_tests.exe;1"
    # http://b/145154677 - adb is not using wmain and fails with an error.
    # "out/soong/.intermediates/system/core/adb/adb_test/windows_x86/adb_test.exe;0"
    "out/soong/.intermediates/build/soong/cc/libbuildversion/tests/build_version_test/windows_x86/build_version_test.exe;0"
    "out/soong/.intermediates/system/core/fastboot/fastboot_test/windows_x86/fastboot_test.exe;0"
    "out/soong/.intermediates/frameworks/base/tools/aapt/libaapt_tests/windows_x86/libaapt_tests.exe;0"
    "out/soong/.intermediates/system/libbase/libbase_test/windows_x86/libbase_test32.exe;1"
    "out/soong/.intermediates/frameworks/base/tools/split-select/libsplit-select_tests/windows_x86/libsplit-select_tests.exe;0"
    "out/soong/.intermediates/system/libziparchive/ziparchive-tests/windows_x86/ziparchive-tests.exe;1"
  )

  local exes_64=(
    "out/soong/.intermediates/frameworks/base/tools/aapt2/aapt2_tests/windows_x86_64/aapt2_tests.exe;1"
    "out/soong/.intermediates/system/libziparchive/ziparchive-tests/windows_x86_64/ziparchive-tests.exe;1"
    "out/soong/.intermediates/frameworks/base/tools/split-select/libsplit-select_tests/windows_x86_64/libsplit-select_tests.exe;0"
    "out/soong/.intermediates/system/libbase/libbase_test/windows_x86_64/libbase_test64.exe;1"
    "out/soong/.intermediates/frameworks/base/tools/aapt/libaapt_tests/windows_x86_64/libaapt_tests.exe;0"
    "out/soong/.intermediates/build/soong/cc/libbuildversion/tests/build_version_test/windows_x86_64/build_version_test.exe;0"
  )

  for index in "${!exes_32[@]}"
  do
    local entry=${exes_32[index]}
    local split=(${entry//;/ })
    local exe=${split[0]}
    local exit_code=${split[1]}
    Path=$TMP_DIR_32 wine $exe 2>/dev/null > $TMP_DIR_32/`basename $exe`.txt
    fail_panic_exit_code $exit_code $exe
  done

  for index in "${!exes_64[@]}"
  do
    local entry=${exes_64[index]}
    local split=(${entry//;/ })
    local exe=${split[0]}
    local exit_code=${split[1]}
    Path=$TMP_DIR_64 wine $exe 2>/dev/null > $TMP_DIR_64/`basename $exe`.txt
    fail_panic_exit_code $exit_code $exe
  done

   Path=$TMP_DIR_32 wine out/host/windows-x86/obj/NATIVE_TESTS/simpleperf_unit_test_intermediates/simpleperf_unit_test.exe -t system/extras/simpleperf/testdata 2> /dev/null > $TMP_DIR_32/simpleperf_unit_test.exe.txt
   Path=$TMP_DIR_64 wine out/host/windows-x86/obj64/NATIVE_TESTS/simpleperf_unit_test_intermediates/simpleperf_unit_test.exe -t system/extras/simpleperf/testdata 2> /dev/null > $TMP_DIR_64/simpleperf_unit_test.exe.txt

  local test=out/soong/.intermediates/system/libziparchive/ziparchive-tests/windows_x86/ziparchive-tests.exe
  cp $test $TMP_DIR_32
  Path=$TMP_DIR_32 wine $TMP_DIR_32/`basename $test` 2> /dev/null > $TMP_DIR_32/`basename $test`.txt

  local test=out/soong/.intermediates/system/libziparchive/ziparchive-tests/windows_x86_64/ziparchive-tests.exe
  cp $test $TMP_DIR_64
  Path=$TMP_DIR_64 wine $TMP_DIR_64/`basename $test` 2> /dev/null > $TMP_DIR_64/`basename $test`.txt
}

make_tmp_dirs
copy_dlls

run_smoke_tests
run_gtests
