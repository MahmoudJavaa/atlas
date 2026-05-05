# Creates a simple .ico file for Atlas SEO using System.Drawing
# Run this once to generate atlas.ico

Add-Type -AssemblyName System.Drawing

$size = 64
$bmp = New-Object System.Drawing.Bitmap($size, $size)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

# Dark background
$bgColor = [System.Drawing.Color]::FromArgb(255, 15, 23, 42)   # slate-900
$g.Clear($bgColor)

# "A" letter in teal
$brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 20, 184, 166))  # teal-500
$font = New-Object System.Drawing.Font("Arial", 38, [System.Drawing.FontStyle]::Bold)
$sf = New-Object System.Drawing.StringFormat
$sf.Alignment = [System.Drawing.StringAlignment]::Center
$sf.LineAlignment = [System.Drawing.StringAlignment]::Center
$rect = New-Object System.Drawing.RectangleF(0, 0, $size, $size)
$g.DrawString("A", $font, $brush, $rect, $sf)

$g.Dispose()

# Save as .ico via memory stream
$ms = New-Object System.IO.MemoryStream
$bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
$ms.Position = 0

# Write ICO header + 64x64 entry manually
$outPath = Join-Path $PSScriptRoot "atlas.ico"
$out = New-Object System.IO.BinaryWriter([System.IO.File]::Create($outPath))

$pngData = $ms.ToArray()
$pngSize = $pngData.Length

# ICO header (6 bytes)
$out.Write([uint16]0)        # reserved
$out.Write([uint16]1)        # type: icon
$out.Write([uint16]1)        # count: 1 image

# ICONDIRENTRY (16 bytes)
$out.Write([byte]0)          # width: 0 = 256 (we use 64, write 64)
$out.Write([byte]0)          # height
$out.Write([byte]0)          # color count
$out.Write([byte]0)          # reserved
$out.Write([uint16]1)        # planes
$out.Write([uint16]32)       # bit count
$out.Write([uint32]$pngSize) # size of image data
$out.Write([uint32]22)       # offset to image data (6 + 16 = 22)

# Image data (PNG)
$out.Write($pngData)
$out.Close()
$bmp.Dispose()

Write-Output "Created: $outPath"
