#define INITGUID
#include <windows.h>
#include <dbgeng.h>
#include <cstdio>
#include <cstring>

// Task-owned diagnostic launcher. No registry or system debugger settings.
struct ConsoleCallbacks : IDebugOutputCallbacks {
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID id, void **out) override {
        if (id == IID_IUnknown || id == IID_IDebugOutputCallbacks) {
            *out = this; return S_OK;
        }
        *out = nullptr; return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return 1; }
    ULONG STDMETHODCALLTYPE Release() override { return 1; }
    HRESULT STDMETHODCALLTYPE Output(ULONG, PCSTR text) override {
        std::fputs(text, stdout); std::fflush(stdout); return S_OK;
    }
};

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    HMODULE library = LoadLibraryA("dbgeng.dll");
    if (!library) { std::printf("LoadLibrary: %lu\n", GetLastError()); return 65; }
    auto create = reinterpret_cast<HRESULT (WINAPI *)(REFIID, void **)>(
        GetProcAddress(library, "DebugCreate"));
    IDebugClient *client = nullptr;
    HRESULT hr = create(IID_IDebugClient, reinterpret_cast<void **>(&client));
    if (FAILED(hr)) return 66;
    IDebugControl *control = nullptr;
    hr = client->QueryInterface(IID_IDebugControl, reinterpret_cast<void **>(&control));
    if (FAILED(hr)) return 67;
    ConsoleCallbacks output;
    client->SetOutputCallbacks(&output);
    client->SetOutputMask(DEBUG_OUTPUT_NORMAL | DEBUG_OUTPUT_ERROR | DEBUG_OUTPUT_WARNING);
    control->AddEngineOptions(DEBUG_ENGOPT_INITIAL_BREAK);
    hr = client->CreateProcessAndAttach(0, argv[1], DEBUG_ONLY_THIS_PROCESS | CREATE_NO_WINDOW, 0, 0);
    if (FAILED(hr)) { std::printf("Create: %lx\n", hr); return 68; }
    hr = control->WaitForEvent(0, 60000);
    if (FAILED(hr)) { std::printf("InitialWait: %lx\n",hr); client->TerminateProcesses(); return 69; }
    control->Execute(DEBUG_OUTCTL_THIS_CLIENT, "sxe 0xc0000374; sxe av; .symfix .work/0.1.0-software-completion-20261101/debug-tools/symbols", DEBUG_EXECUTE_DEFAULT);
    control->SetExecutionStatus(DEBUG_STATUS_GO);
    for (int attempt = 0; attempt < 120; ++attempt) {
        hr = control->WaitForEvent(0, 10000);
        if (hr == S_FALSE) continue;
        ULONG status = 0;
        control->GetExecutionStatus(&status);
        if (status == DEBUG_STATUS_NO_DEBUGGEE) { std::puts("DEBUGGEE_EXITED"); return 0; }
        if (FAILED(hr)) { std::printf("Wait: %lx\n", hr); client->TerminateProcesses(); return 70; }
        ULONG type = 0, pid = 0, tid = 0, used = 0;
        DEBUG_LAST_EVENT_INFO_EXCEPTION info = {};
        control->GetLastEventInformation(&type, &pid, &tid, &info, sizeof(info), &used, nullptr, 0, nullptr);
        std::printf("EVENT type=%lu pid=%lu tid=%lu code=%lx first=%lu\n", type, pid, tid, info.ExceptionRecord.ExceptionCode, info.FirstChance);
        if (type == DEBUG_EVENT_EXCEPTION &&
            (info.ExceptionRecord.ExceptionCode == 0xc0000374 || info.ExceptionRecord.ExceptionCode == EXCEPTION_ACCESS_VIOLATION)) {
            control->Execute(DEBUG_OUTCTL_THIS_CLIENT, ".ecxr; kv 60; ~* k 30; lm", DEBUG_EXECUTE_DEFAULT);
            control->Execute(DEBUG_OUTCTL_THIS_CLIENT, ".dump /m .work/0.1.0-software-completion-20261101/debug-tools/crash.dmp", DEBUG_EXECUTE_DEFAULT);
            client->TerminateProcesses();
            client->EndSession(DEBUG_END_ACTIVE_TERMINATE);
            return 2;
        }
        control->SetExecutionStatus(DEBUG_STATUS_GO);
    }
    client->TerminateProcesses();
    return 71;
}


