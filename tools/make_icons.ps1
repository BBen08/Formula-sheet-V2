<#
  make_icons.ps1 - Make the app icons from the logo picture.

  Run once (or again when you change the logo), from the formula-app folder:
      powershell -ExecutionPolicy Bypass -File tools\make_icons.ps1

  It uses Windows' built-in image tools (no Python packages needed) and writes:
      src/static/icons/apple-touch-icon.png  180x180  iPhone / iPad Home Screen
      src/static/icons/icon-192.png          192x192  Android, desktop
      src/static/icons/icon-512.png          512x512  install screens
      src/static/icons/maskable-512.png      512x512  Android (logo shrunk to fit any shape)
      src/static/icons/favicon-32.png         32x32   browser tab

  The logo picture has a dark margin around the rounded tile. $Crop below
  is the square around just the tile (x, y, size) in the original picture.
#>
param(
  [string]$Logo = "assets\logo.webp",
  [int[]]$Crop = @(128, 120, 996),
  [string]$OutDir = "src\static\icons"
)

Add-Type -AssemblyName PresentationCore, PresentationFramework, WindowsBase
$ErrorActionPreference = "Stop"

$stream = [IO.File]::OpenRead((Resolve-Path $Logo))
$decoder = [Windows.Media.Imaging.BitmapDecoder]::Create($stream, 'None', 'OnLoad')
$stream.Close()
$full = $decoder.Frames[0]
$tile = New-Object Windows.Media.Imaging.CroppedBitmap($full, (New-Object Windows.Int32Rect($Crop[0], $Crop[1], $Crop[2], $Crop[2])))

# Colour of the tile itself, used to fill corners and padding.
$px = New-Object byte[] 4
$full.CopyPixels((New-Object Windows.Int32Rect(($Crop[0] + 20), ($Crop[1] + $Crop[2] / 2), 1, 1)), $px, 4, 0)
$tileColor = [Windows.Media.Color]::FromRgb($px[2], $px[1], $px[0])
New-Item -ItemType Directory -Force $OutDir | Out-Null

function Save-Icon([string]$Name, [int]$Size, [double]$Scale, [bool]$Fill, [bool]$Round) {
  $visual = New-Object Windows.Media.DrawingVisual
  $dc = $visual.RenderOpen()
  $full_rect = New-Object Windows.Rect(0, 0, $Size, $Size)
  if ($Fill) { $dc.DrawRectangle((New-Object Windows.Media.SolidColorBrush($tileColor)), $null, $full_rect) }
  $inner = $Size * $Scale
  $offset = ($Size - $inner) / 2
  $rect = New-Object Windows.Rect($offset, $offset, $inner, $inner)
  if ($Round) {
    $radius = $inner * 0.22
    $dc.PushClip((New-Object Windows.Media.RectangleGeometry($rect, $radius, $radius)))
  }
  $dc.DrawImage($tile, $rect)
  if ($Round) { $dc.Pop() }
  $dc.Close()

  $bitmap = New-Object Windows.Media.Imaging.RenderTargetBitmap($Size, $Size, 96, 96, [Windows.Media.PixelFormats]::Pbgra32)
  $bitmap.Render($visual)
  $encoder = New-Object Windows.Media.Imaging.PngBitmapEncoder
  $encoder.Frames.Add([Windows.Media.Imaging.BitmapFrame]::Create($bitmap))
  $path = Join-Path $OutDir $Name
  $out = [IO.File]::Create($path)
  $encoder.Save($out)
  $out.Close()
  Write-Output "  wrote $path"
}

# iPhone adds its own rounded corners and does not allow transparency: fill the square.
Save-Icon "apple-touch-icon.png" 180 1.0 $true $true
# Desktop / Android "any" icons: rounded tile on a transparent background.
Save-Icon "icon-192.png" 192 1.0 $false $true
Save-Icon "icon-512.png" 512 1.0 $false $true
Save-Icon "favicon-32.png" 32 1.0 $false $true
# Android crops "maskable" icons to circles etc.: keep the logo inside the middle 80%.
Save-Icon "maskable-512.png" 512 0.8 $true $true
