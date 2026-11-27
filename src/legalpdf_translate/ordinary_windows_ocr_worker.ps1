# Fixed stdin/stdout worker. It accepts no arguments or paths.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$VerbosePreference = 'SilentlyContinue'
$WarningPreference = 'SilentlyContinue'
$InformationPreference = 'SilentlyContinue'
$maxBytes = 16777216
$maxSide = 4096
$maxPixels = 16000000
$maxOutput = 1048576
if ($args.Count -ne 0) { exit 2 }

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
    $null = [Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
    $null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
    $null = [Windows.Media.Ocr.OcrResult,Windows.Foundation,ContentType=WindowsRuntime]
    $null = [Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Length -eq 1 -and
        $_.GetParameters().Length -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    if ($null -eq $asTask) { exit 2 }
    function Resolve-Operation($operation, [Type]$type) {
        $task = $asTask.MakeGenericMethod($type).Invoke($null, @($operation))
        if (-not $task.Wait(8000)) { throw 'timeout' }
        $task.Result
    }

    $memory = [IO.MemoryStream]::new()
    try {
        $inputStream = [Console]::OpenStandardInput()
        $buffer = [byte[]]::new(65536)
        while (($count = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            if ($memory.Length + $count -gt $maxBytes) { throw 'input limit' }
            $memory.Write($buffer, 0, $count)
        }
        if ($memory.Length -lt 45) { throw 'invalid PNG' }
        $memory.Position = 0
        $stream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($memory)
        try {
            $decoder = Resolve-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
            $width = [long]$decoder.PixelWidth
            $height = [long]$decoder.PixelHeight
            if ($decoder.DecoderInformation.CodecId -ne [Windows.Graphics.Imaging.BitmapDecoder]::PngDecoderId -or
                $width -lt 1 -or $height -lt 1 -or $width -gt $maxSide -or $height -gt $maxSide -or
                $width * $height -gt $maxPixels -or
                [Math]::Max($width, $height) -gt [Windows.Media.Ocr.OcrEngine]::MaxImageDimension) { throw 'invalid image' }
            $language = [Windows.Globalization.Language]::new('pt-PT')
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
            if ($null -eq $engine) { throw 'language unavailable' }
            $bitmap = Resolve-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
            try {
                if ($bitmap.PixelWidth -ne $width -or $bitmap.PixelHeight -ne $height) { throw 'dimensions changed' }
                $result = Resolve-Operation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
                $linesSeen = 0
                $wordsSeen = 0
                $charsSeen = 0
                $lines = @(foreach ($line in $result.Lines) {
                    $linesSeen += 1
                    $charsSeen += $line.Text.Length
                    if ($linesSeen -gt 1000 -or $charsSeen -gt 64000 -or $line.Text.Length -gt 4096) { throw 'text limit' }
                    [pscustomobject]@{
                        text = $line.Text
                        words = @(foreach ($word in $line.Words) {
                            $wordsSeen += 1
                            if ($wordsSeen -gt 6000) { throw 'word limit' }
                            $rect = $word.BoundingRect
                            [pscustomobject]@{text=$word.Text; box=@($rect.X, $rect.Y, $rect.Width, $rect.Height)}
                        })
                    }
                })
                $json = [pscustomobject]@{version=1; language='pt-PT'; width=$width; height=$height; lines=$lines} |
                    ConvertTo-Json -Depth 7 -Compress
                $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json)
                if ($bytes.Length -gt $maxOutput) { throw 'output limit' }
                $outputStream = [Console]::OpenStandardOutput()
                $outputStream.Write($bytes, 0, $bytes.Length)
                $outputStream.Flush()
            } finally { $bitmap.Dispose() }
        } finally { $stream.Dispose() }
    } finally { $memory.Dispose() }
    exit 0
} catch {
    # No raster, text, user environment or diagnostic is emitted on failure.
    exit 2
}
