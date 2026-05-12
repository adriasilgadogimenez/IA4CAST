; ============================================================
; IA4CAST - Inno Setup script
; Instalador con pagina personalizada para configurar SQL Server.
;
; Genera installer\IA4CAST_Setup_v1.0.exe
;
; Pasos del wizard:
;   1. Bienvenida (estandar)
;   2. Carpeta de instalacion (estandar)
;   3. Configuracion SQL Server (PERSONALIZADA, opcional)
;   4. Iconos (estandar)
;   5. Instalacion (estandar)
;   6. Finalizacion (estandar)
; ============================================================

#define MyAppName "IA4CAST"
#define MyAppVersion "1.0"
#define MyAppPublisher "Projecte IA4CAST"
#define MyAppExeName "IA4CAST.exe"

[Setup]
AppId={{B9F3A2C8-4D5E-4F6A-9B8C-7E1D2A3B4C5D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=IA4CAST_Setup_v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
DisableProgramGroupPage=yes
SetupIconFile=ia4cast\resources\icono.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "catalan"; MessagesFile: "compiler:Languages\Catalan.isl"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "config\default.yaml"; DestDir: "{app}\config"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; \
    GroupDescription: "Iconos adicionales:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar IA4CAST"; \
    Flags: nowait postinstall skipifsilent

; ============================================================
; CODIGO PASCAL: paginas personalizadas y logica
; ============================================================
[Code]
var
  // Pagina de configuracion SQL
  SqlPage: TInputQueryWizardPage;
  SqlEnableCheckPage: TInputOptionWizardPage;
  ConfigurarSqlAhora: Boolean;

// ------------------------------------------------------------
// InitializeWizard: crea las paginas personalizadas
// ------------------------------------------------------------
procedure InitializeWizard;
begin
  // Pagina 1: preguntar si quiere configurar SQL ahora
  SqlEnableCheckPage := CreateInputOptionPage(wpSelectDir,
    'Configuracion de SQL Server',
    'Configuracion opcional de la base de datos corporativa',
    'IA4CAST puede conectarse a una base de datos SQL Server para cargar datos masivos. ' +
    'Tambien puedes trabajar siempre con ficheros Excel/CSV/ODS sin necesidad de conectarte.' + #13#10 + #13#10 +
    'Si no estas seguro, salta este paso. Podras configurarlo mas tarde desde la propia aplicacion.',
    True, False);
  SqlEnableCheckPage.Add('Configurar SQL Server ahora');
  SqlEnableCheckPage.Add('Saltar esta configuracion (usar solo ficheros)');
  SqlEnableCheckPage.SelectedValueIndex := 1;  // por defecto, saltar

  // Pagina 2: datos de conexion (se mostrara o saltara segun la eleccion)
  SqlPage := CreateInputQueryPage(SqlEnableCheckPage.ID,
    'Datos de conexion a SQL Server',
    'Introduce los datos del servidor de base de datos',
    'Estos datos se guardaran en el fichero de configuracion. La contrasenya se cifrara ' +
    'automaticamente con Fernet la primera vez que se ejecute la aplicacion.');
  SqlPage.Add('Servidor (host):', False);
  SqlPage.Add('Puerto:', False);
  SqlPage.Add('Base de datos:', False);
  SqlPage.Add('Usuario:', False);
  SqlPage.Add('Contrasenya:', True);  // True = ocultar texto

  // Valores por defecto
  SqlPage.Values[0] := 'localhost';
  SqlPage.Values[1] := '1433';
  SqlPage.Values[2] := 'vendes';
  SqlPage.Values[3] := 'ia4cast_ro';
  SqlPage.Values[4] := '';
end;

// ------------------------------------------------------------
// ShouldSkipPage: salta la pagina de datos si el usuario eligio "Saltar"
// ------------------------------------------------------------
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = SqlPage.ID then
    Result := (SqlEnableCheckPage.SelectedValueIndex = 1);
end;

// ------------------------------------------------------------
// NextButtonClick: valida los campos antes de continuar
// ------------------------------------------------------------
function NextButtonClick(CurPageID: Integer): Boolean;
var
  i: Integer;
begin
  Result := True;
  if (CurPageID = SqlPage.ID) and (SqlEnableCheckPage.SelectedValueIndex = 0) then
  begin
    // Validar que no esten vacios
    for i := 0 to 4 do
    begin
      if Trim(SqlPage.Values[i]) = '' then
      begin
        MsgBox('Todos los campos son obligatorios.', mbError, MB_OK);
        Result := False;
        Exit;
      end;
    end;
    ConfigurarSqlAhora := True;
  end;
end;

// ------------------------------------------------------------
// EscaparYaml: escapa comillas dobles en valores YAML
// ------------------------------------------------------------
function EscaparYaml(const S: String): String;
var
  i: Integer;
  R: String;
begin
  R := '';
  for i := 1 to Length(S) do
  begin
    if S[i] = '"' then
      R := R + '\"'
    else if S[i] = '\' then
      R := R + '\\'
    else
      R := R + S[i];
  end;
  Result := R;
end;

// ------------------------------------------------------------
// CrearConfigPersonalizado: genera el fichero de marcador para
// que la app sepa en el primer arranque que tiene que leer los
// datos de SQL guardados aqui
// ------------------------------------------------------------
procedure CrearConfigPersonalizado;
var
  Contenido: TStringList;
  RutaConfig: String;
begin
  if not ConfigurarSqlAhora then
    Exit;

  // Guardamos un fichero TEMPORAL con los datos en {app}\config\
  // La app, en el primer arranque, lo leera, copiara los datos a
  // %APPDATA%\IA4CAST\config.yaml (cifrando la contrasenya con Fernet)
  // y borrara el fichero temporal.
  RutaConfig := ExpandConstant('{app}\config\sql_install_data.txt');

  Contenido := TStringList.Create;
  try
    Contenido.Add('# Datos recogidos durante la instalacion');
    Contenido.Add('# La app los procesara en el primer arranque y borrara este fichero');
    Contenido.Add('host=' + SqlPage.Values[0]);
    Contenido.Add('port=' + SqlPage.Values[1]);
    Contenido.Add('database=' + SqlPage.Values[2]);
    Contenido.Add('user=' + SqlPage.Values[3]);
    Contenido.Add('password=' + SqlPage.Values[4]);
    Contenido.SaveToFile(RutaConfig);
  finally
    Contenido.Free;
  end;
end;

// ------------------------------------------------------------
// CurStepChanged: hook al final de la instalacion para crear el fichero
// ------------------------------------------------------------
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    CrearConfigPersonalizado;
end;
