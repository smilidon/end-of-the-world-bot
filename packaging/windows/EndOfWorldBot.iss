#ifndef Version
  #define Version "0.0.0-dev"
#endif
#ifndef SourceDir
  #define SourceDir "..\.."
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

[Setup]
AppId={{E643B587-1C4B-4B1F-87FD-14992334416B}
AppName=End of the World Bot
AppVersion={#Version}
AppPublisher=JLP Computer LLC
DefaultDirName={localappdata}\Programs\EndOfWorldBot
DefaultGroupName=End of the World Bot
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=EndOfWorldBot-Windows-Setup-{#Version}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=End of the World Bot
SetupLogging=yes

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\End of the World Bot Setup"; Filename: "{app}\windows\EndOfWorldBot-Setup.cmd"; WorkingDir: "{app}\windows"
Name: "{group}\Windows install guide"; Filename: "{app}\docs\WINDOWS_INSTALL.md"
Name: "{group}\Project folder"; Filename: "{app}"

[Run]
Filename: "{app}\windows\EndOfWorldBot-Setup.cmd"; Description: "Run the Windows/WSL setup assistant"; Flags: postinstall nowait skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
