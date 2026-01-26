; *** Inno Setup version 6.0.0+ Chinese (Simplified) messages ***
;
; To download user-contributed translations of this file, go to:
;   http://www.jrsoftware.org/files/istrans/
;
; Note: When translating this file, do not translate the strings in the
; "Setup" section.

[LangOptions]
; The following three entries are very important. Be sure to read the 
; section "Language Options" in the help file.

LanguageName=Chinese (Simplified)
LanguageID=$0804
LanguageCodePage=936
; If the language you are translating to requires special font faces or
; sizes, uncomment any of the following entries and change them accordingly.
;DialogFontName=
;DialogFontSize=8
;WelcomeFontName=Verdana
;WelcomeFontSize=12
;TitleFontName=Arial
;TitleFontSize=29
;CopyrightFontName=Arial
;CopyrightFontSize=8

[Messages]

; *** Application titles
SetupAppTitle=安装
SetupWindowTitle=安装 - %1
UninstallAppTitle=卸载
UninstallAppFullTitle=%1 卸载

; *** Misc. common
InformationTitle=信息
ConfirmTitle=确认
ErrorTitle=错误

; *** SetupLdr messages
SetupLdrStartupMessage=这将安装 %1。是否确定要继续？
LdrCannotCreateTemp=无法创建临时文件。安装程序中止
LdrCannotExecTemp=无法执行临时文件。安装程序中止

; *** Startup error messages
LastErrorMessage=%1.%n%n错误 %2: %3
SetupFileMissing=安装目录中的文件 %1 丢失。请更正这个问题或获取一个新的程序副本。
SetupFileCorrupt=安装文件已损坏。请获取一个新的程序副本。
SetupFileCorruptOrWrongVer=安装文件已损坏，或是与这个安装程序的版本不兼容。请更正这个问题或获取一个新的程序副本。
InvalidParameter=无效的命令行参数: %n%n%1
SetupAlreadyRunning=安装程序已经运行。
WindowsVersionNotSupported=这个程序不支持您的计算机运行的 Windows 版本。
WindowsServicePackRequired=这个程序要求 %1 Service Pack %2 或更高。
NotOnThisPlatform=这个程序将不能在 %1 上运行。
OnlyOnThisPlatform=这个程序必须在 %1 上运行。
OnlyOnTheseArchitectures=这个程序只能在专为处理器架构设计的 Windows 版本上安装: %n%n%1
WinVersionTooLowError=这个程序要求 %1 版本 %2 或更高。
WinVersionTooHighError=这个程序不能安装在 %1 版本 %2 或更高。
AdminPrivilegesRequired=在安装这个程序时您必须以此计算机的“管理员”身份登录。
PowerUserPrivilegesRequired=在安装这个程序时您必须以此计算机的“管理员”或“有权限的用户”身份登录。
SetupAppRunningError=安装程序检测到 %1 当前正在运行。%n%n请先关闭它的所有实例，然后单击“确定”继续，或单击“取消”退出。
UninstallAppRunningError=卸载程序检测到 %1 当前正在运行。%n%n请先关闭它的所有实例，然后单击“确定”继续，或单击“取消”退出。

; *** Startup questions
PrivilegesRequiredOverrideTitle=选择安装模式
PrivilegesRequiredOverrideInstruction=选择安装模式
PrivilegesRequiredOverrideText1=%1 可以为所有用户安装(需要管理权限)，或仅为您安装。
PrivilegesRequiredOverrideText2=%1 只能为您安装，或为所有用户安装(需要管理权限)。
PrivilegesRequiredOverrideAllUsers=为所有用户安装
PrivilegesRequiredOverrideAllUsersRecommended=为所有用户安装(建议)
PrivilegesRequiredOverrideCurrentUser=仅为我安装
PrivilegesRequiredOverrideCurrentUserRecommended=仅为我安装(建议)

; *** Misc. errors
ErrorCreatingDir=安装程序无法创建目录“%1”
ErrorTooManyFilesInDir=无法在目录“%1”中创建文件，因为里面的文件太多了

; *** Setup common messages
ExitSetupTitle=退出安装程序
ExitSetupMessage=安装程序未完成安装。如果您现在退出，程序将不会被安装。%n%n您可以以后再运行安装程序来完成安装。%n%n退出安装程序吗？
AboutSetupMenuItem=关于安装程序(&A)...
AboutSetupTitle=关于安装程序
AboutSetupMessage=%1 版本 %2%n%3%n%n%1 主页:%n%4
AboutSetupNote=
TranslatorNote=

; *** Buttons
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安装(&I)
ButtonOK=确定
ButtonCancel=取消
ButtonYes=是(&Y)
ButtonYesToAll=全是(&A)
ButtonNo=否(&N)
ButtonNoToAll=全否(&O)
ButtonFinish=完成(&F)
ButtonBrowse=浏览(&B)...
ButtonWizardBrowse=浏览(&R)...
ButtonNewFolder=新建文件夹(&M)

; *** "Select Language" dialog messages
SelectLanguageTitle=选择安装语言
SelectLanguageLabel=选择安装时要使用的语言:

; *** Common wizard text
ClickNext=单击“下一步”继续，或单击“取消”退出安装程序。
BeveledLabel=
BrowseDialogTitle=浏览文件夹
BrowseDialogLabel=在下面的列表中选择一个文件夹，然后单击“确定”。
NewFolderName=新文件夹

; *** "Welcome" wizard page
WelcomeLabel1=欢迎使用 [name] 安装向导
WelcomeLabel2=此程序将安装 [name/ver] 到您的计算机中。%n%n建议您在继续安装之前关闭所有其它应用程序。

; *** "Password" wizard page
WizardPassword=密码
PasswordLabel1=这个安装程序受密码保护。
PasswordLabel3=请输入密码，然后单击“下一步”继续。密码区分大小写。
PasswordEditLabel=密码(&P):
IncorrectPassword=您输入的密码不正确，请重试。

; *** "License Agreement" wizard page
WizardLicense=许可协议
LicenseLabel1=在继续安装之前，请阅读下列重要信息。
LicenseLabel3=请阅读下列许可协议。在继续安装之前，您必须接受此协议的条款。
LicenseAccepted=我接受协议(&A)
LicenseNotAccepted=我不接受协议(&D)

; *** "Information" wizard pages
WizardInfoBefore=信息
InfoBeforeLabel=在继续安装之前，请阅读下列重要信息。
InfoBeforeClickLabel=准备好继续安装后，单击“下一步”。
WizardInfoAfter=信息
InfoAfterLabel=在继续安装之前，请阅读下列重要信息。
InfoAfterClickLabel=准备好继续安装后，单击“下一步”。

; *** "User Information" wizard page
WizardUserInfo=用户信息
UserInfoDesc=请输入您的信息。
UserInfoName=用户名(&U):
UserInfoOrg=组织(&O):
UserInfoSerial=序列号(&S):
UserInfoNameRequired=您必须输入一个名称。

; *** "Select Destination Location" wizard page
WizardSelectDir=选择目标位置
SelectDirDesc=您想将 [name] 安装在哪里？
SelectDirLabel3=安装程序将安装 [name] 到下列文件夹中。
SelectDirBrowseLabel=单击“下一步”继续。如果您想选择其它文件夹，单击“浏览”。
DiskSpaceMBLabel=至少需要有 [mb] MB 的可用磁盘空间。
CannotInstallToNetworkDrive=安装程序无法安装到网络驱动器。
CannotInstallToUNCPath=安装程序无法安装到 UNC 路径。
InvalidPath=您必须输入一个完整的路径，例如:%n%nC:\APP%n%n或一个 UNC 路径，例如:%n%n\\server\share
InvalidDrive=您选择的驱动器或 UNC 共享不存在或不能访问。请选择其它位置。
DiskSpaceWarningTitle=磁盘空间不足
DiskSpaceWarning=安装程序至少需要 %1 KB 的可用磁盘空间才能安装，但选定驱动器只有 %2 KB 的可用空间。%n%n是否确定要继续？
DirNameTooLong=文件夹名称或路径太长。
InvalidDirName=文件夹名称无效。
BadDirName32=文件夹名称不能包含下列字符:%n%n%1
DirExistsTitle=文件夹已存在
DirExists=文件夹:%n%n%1%n%n已经存在。您想在这个文件夹中安装吗？
DirDoesntExistTitle=文件夹不存在
DirDoesntExist=文件夹:%n%n%1%n%n不存在。您想创建该文件夹吗？

; *** "Select Components" wizard page
WizardSelectComponents=选择组件
SelectComponentsDesc=您想安装哪些组件？
SelectComponentsLabel2=选择您想安装的组件；清除您不想安装的组件。准备好后，单击“下一步”。
FullInstallation=完全安装
; if possible don't translate 'Compact' as 'Minimal' (I mean 'Minimal' in your language)
CompactInstallation=简洁安装
CustomInstallation=自定义安装
NoUninstallWarningTitle=组件已存在
NoUninstallWarning=安装程序检测到下列组件已在您的计算机中安装:%n%n%1%n%n取消选择这些组件将不会卸载它们。%n%n是否确定要继续？
ComponentSize1=%1 KB
ComponentSize2=%1 MB
ComponentsDiskSpaceMBLabel=当前选择至少需要 [mb] MB 的可用磁盘空间。

; *** "Select Additional Tasks" wizard page
WizardSelectTasks=选择附加任务
SelectTasksDesc=您想执行哪些附加任务？
SelectTasksLabel2=选择您想安装程序执行的附加任务，然后单击“下一步”。

; *** "Select Start Menu Folder" wizard page
WizardSelectProgramGroup=选择开始菜单文件夹
SelectStartMenuFolderDesc=您想在哪里放置程序的快捷方式？
SelectStartMenuFolderLabel3=安装程序将在下列“开始”菜单文件夹中创建程序的快捷方式。
SelectStartMenuFolderBrowseLabel=单击“下一步”继续。如果您想选择其它文件夹，单击“浏览”。
MustEnterGroupName=您必须输入一个文件夹名称。
GroupNameTooLong=文件夹名称或路径太长。
InvalidGroupName=文件夹名称无效。
BadGroupName=文件夹名称不能包含下列字符:%n%n%1
NoProgramGroupCheck2=不创建“开始”菜单文件夹(&D)

; *** "Ready to Install" wizard page
WizardReady=准备安装
ReadyLabel1=安装程序现在准备开始安装 [name] 到您的计算机中。
ReadyLabel2a=单击“安装”继续此安装程序。如果您想回顾或改变设置，请单击“上一步”。
ReadyLabel2b=单击“安装”继续此安装程序？
ReadyMemoUserInfo=用户信息:
ReadyMemoDir=目标位置:
ReadyMemoType=安装类型:
ReadyMemoComponents=选定组件:
ReadyMemoGroup=“开始”菜单文件夹:
ReadyMemoTasks=附加任务:

; *** "Preparing to Install" wizard page
WizardPreparing=正在准备安装
PreparingDesc=安装程序正在准备安装 [name] 到您的计算机中。
PreviousInstallNotCompleted=先前的程序安装/卸载未完成。您需要重新启动计算机才能完成安装。%n%n在重新启动计算机后，请再次运行安装程序来完成安装 [name]。
CannotContinue=安装程序无法继续。请单击“取消”退出。
ApplicationsFound=下列应用程序正在使用需要更新的文件。建议您允许安装程序自动关闭并重启这些应用程序。
ApplicationsFound2=下列应用程序正在使用需要更新的文件。建议您允许安装程序自动关闭这些应用程序。在安装完成后，安装程序将尝试重启这些应用程序。
CloseApplications=自动关闭并尝试重启应用程序(&A)
DontCloseApplications=不要关闭应用程序(&D)
ErrorCloseApplications=安装程序无法自动关闭所有应用程序。建议您在继续安装之前关闭所有使用需要更新的文件的应用程序。

; *** "Installing" wizard page
WizardInstalling=正在安装
InstallingLabel=安装程序正在安装 [name] 到您的计算机中，请稍候。

; *** "Setup Completed" wizard page
FinishedHeadingLabel=[name] 安装向导完成
FinishedLabelNoIcons=安装程序已在您的计算机中安装了 [name]。
FinishedLabel=安装程序已在您的计算机中安装了 [name]。可以通过选择已安装的图标运行应用程序。
ClickFinish=单击“完成”退出安装程序。
FinishedRestartLabel=为了完成 [name] 的安装，安装程序必须重新启动您的计算机。是否立即重新启动？
FinishedRestartMessage=为了完成 [name] 的安装，安装程序必须重新启动您的计算机。%n%n是否立即重新启动？
ShowReadmeCheck=是，我想阅读自述文件
YesRadio=是，立即重新启动计算机(&Y)
NoRadio=否，我稍后重新启动计算机(&N)
; used for example as 'Run MyProg.exe'
RunEntryExec=运行 %1
; used for example as 'View Readme.txt'
RunEntryShellExec=查看 %1

; *** "Setup Needs the Next Disk" stuff
ChangeDiskTitle=下一个磁盘
SelectDiskLabel2=请插入磁盘 %1 并单击“确定”。%n%n如果这个磁盘中的文件可以在其它文件夹中找到，请输入正确的路径或单击“浏览”。
PathLabel=路径(&P):
FileNotInDir2=在“%2”中无法找到文件“%1”。请插入正确的磁盘或选择其它文件夹。
SelectDirectoryLabel=请输入下一个磁盘的位置。

; *** Installation phase messages
SetupAborted=安装程序未完成安装。%n%n请更正问题并再次运行安装程序。
AbortRetryIgnoreSelectAction=选择操作
AbortRetryIgnoreRetry=重试(&T)
AbortRetryIgnoreIgnore=忽略错误并继续(&I)
AbortRetryIgnoreCancel=取消安装

; *** Installation status messages
StatusClosingApplications=正在关闭应用程序...
StatusCreateDirs=正在创建目录...
StatusExtractFiles=正在解压文件...
StatusCreateIcons=正在创建快捷方式...
StatusCreateIniEntries=正在创建 INI 条目...
StatusCreateRegistryEntries=正在创建注册表项...
StatusRegisterFiles=正在注册文件...
StatusSavingUninstall=正在保存卸载信息...
StatusRunProgram=正在完成安装...
StatusRestartingApplications=正在重启应用程序...
StatusRollback=正在撤销更改...

; *** Misc. errors
ErrorInternal2=内部错误: %1
ErrorFunctionFailedNoCode=%1 失败
ErrorFunctionFailed=%1 失败; 代码 %2
ErrorFunctionFailedWithMessage=%1 失败; 代码 %2.%n%3
ErrorExecutingROW=在执行文件时出错:%n%1
; The following can be used in the {uninstallexe} constant
SetupAppInstanceCannotBeClosed=下列应用程序正在使用安装程序所需的文件，并且无法被关闭:%n%n%1%n%n请关闭应用程序并单击“重试”继续，或单击“取消”退出。
ObsoleteOption=检测到过时的消息 ID "%1"

; *** Watched setup common messages
WatchedSetupError=安装程序检测到 %1 正在运行。%n%n请关闭它的所有实例，然后单击“重试”继续，或单击“取消”退出。

; *** Uninstall common messages
UninstallStatusLabel=正在从您的计算机中删除 [name]，请稍候。
UninstallNotCompleted=卸载程序未完成卸载。%n%n请更正问题并再次运行卸载程序。
UninstallAborted=卸载程序未完成卸载。
UninstallOpenError=文件“%1”无法打开。无法卸载。
UninstallNotFound=文件“%1”不存在。无法卸载。
UninstallUnknownEntry=在卸载日志中遇到未知条目 (%1)
ConfirmUninstall=您确定要从计算机中完全删除 %1 及其所有组件吗？
UninstallOnlyOnWin64=这个程序只能在 64 位 Windows 上卸载。
OnlyAdminCanUninstall=这个安装程序只有在您具有管理员权限时才能卸载。
UninstallStatusMsg1=正在删除 %1...
UninstallStatusMsg2=正在删除 %1...
UninstallStatusMsg3=正在删除 %1...
UninstallRunEntry=运行 %1
ConnectedApplicationsUrlMessage=检测到下列应用程序正在运行:%n%n%1%n%n请关闭所有这些应用程序，然后单击“重试”继续，或单击“取消”退出。
UninstallNotFound=文件“%1”不存在。无法卸载。
UninstallUnknownEntry=在卸载日志中遇到未知条目 (%1)
ConfirmUninstall=您确定要从计算机中完全删除 %1 及其所有组件吗？
