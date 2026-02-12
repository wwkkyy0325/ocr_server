#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef DEBUG_MODE
int main(int argc, char *argv[]) {
#else
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
#endif
    char exePath[MAX_PATH];
    char drive[_MAX_DRIVE];
    char dir[_MAX_DIR];
    char fname[_MAX_FNAME];
    char ext[_MAX_EXT];
    char cwd[MAX_PATH];
    char pythonPath[MAX_PATH];
    char bootScript[MAX_PATH];
    char cmdLine[MAX_PATH * 4];
    char pythonEnv[MAX_PATH * 4];
    
    // Get the path of the current executable
    if (GetModuleFileName(NULL, exePath, MAX_PATH) == 0) {
#ifdef DEBUG_MODE
        printf("Failed to get executable path.\n");
        system("pause");
#else
        MessageBox(NULL, "Failed to get executable path.", "Error", MB_OK | MB_ICONERROR);
#endif
        return 1;
    }

    // Split path to get directory
    _splitpath(exePath, drive, dir, fname, ext);
    _makepath(cwd, drive, dir, NULL, NULL);

    // Set current directory to the executable's directory
    if (!SetCurrentDirectory(cwd)) {
#ifdef DEBUG_MODE
        printf("Failed to set current directory.\n");
        system("pause");
#else
        MessageBox(NULL, "Failed to set current directory.", "Error", MB_OK | MB_ICONERROR);
#endif
        return 1;
    }

    // Construct paths
#ifdef DEBUG_MODE
    sprintf(pythonPath, "%sbase_env\\python.exe", cwd);
#else
    sprintf(pythonPath, "%sbase_env\\pythonw.exe", cwd);
#endif
    sprintf(bootScript, "%sboot.py", cwd);

    // Check if python exists
    if (GetFileAttributes(pythonPath) == INVALID_FILE_ATTRIBUTES) {
        char msg[512];
        sprintf(msg, "Python environment not found at:\n%s\n\nPlease ensure base_env is configured correctly.", pythonPath);
#ifdef DEBUG_MODE
        printf("%s\n", msg);
        system("pause");
#else
        MessageBox(NULL, msg, "Error", MB_OK | MB_ICONERROR);
#endif
        return 1;
    }

    // Set PYTHONPATH environment variable
    // PYTHONPATH=cwd\site_packages;cwd
    sprintf(pythonEnv, "PYTHONPATH=%ssite_packages;%s", cwd, cwd);
    _putenv(pythonEnv);

    // Prepare command line: "pythonw.exe" "boot.py"
    // Note: We quote paths to handle spaces
    sprintf(cmdLine, "\"%s\" \"%s\"", pythonPath, bootScript);

    // Create process
    STARTUPINFO si;
    PROCESS_INFORMATION pi;

    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    // CreateProcess
    // We pass NULL for application name and the full command line for command line
    // We inherit environment (so PYTHONPATH is passed)
#ifdef DEBUG_MODE
    DWORD creationFlags = 0; // Default console
#else
    DWORD creationFlags = CREATE_NO_WINDOW;
#endif

    if (!CreateProcess(NULL,   // No module name (use command line)
        cmdLine,        // Command line
        NULL,           // Process handle not inheritable
        NULL,           // Thread handle not inheritable
        FALSE,          // Set handle inheritance to FALSE
        creationFlags,  // Creation flags
        NULL,           // Use parent's environment block
        NULL,           // Use parent's starting directory 
        &si,            // Pointer to STARTUPINFO structure
        &pi)            // Pointer to PROCESS_INFORMATION structure
    ) {
        char msg[512];
        sprintf(msg, "Failed to launch process.\nError code: %d", GetLastError());
#ifdef DEBUG_MODE
        printf("%s\n", msg);
        system("pause");
#else
        MessageBox(NULL, msg, "Error", MB_OK | MB_ICONERROR);
#endif
        return 1;
    }

    // Close process and thread handles. 
#ifdef DEBUG_MODE
    // Wait for process to finish in debug mode so we can see output
    WaitForSingleObject(pi.hProcess, INFINITE);
#else
    CloseHandle(pi.hProcess);
#endif
    CloseHandle(pi.hThread);

    return 0;
}
