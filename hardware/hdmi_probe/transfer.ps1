param([string]$Archive = 'C:/temp/lesion_hdmi_probe/hdmi_probe.tar.gz')
$ErrorActionPreference = 'Stop'
$payload = [Convert]::ToBase64String([IO.File]::ReadAllBytes($Archive))
$expected = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash.ToLowerInvariant()
$serial = [IO.Ports.SerialPort]::new('COM9',115200,'None',8,'One')
$serial.WriteTimeout = 10000
$serial.ReadBufferSize = 65536
try {
    $serial.Open()
    $serial.DiscardInBuffer()
    # Execute stty separately: the shell defers a compound command until its
    # complete heredoc has been read, which would otherwise echo the payload.
    $serial.Write("stty -echo`r")
    Start-Sleep -Milliseconds 500
    $serial.Write("base64 -d > /tmp/hdmi_probe.tar.gz <<'HDMI_PROBE_PAYLOAD_END'`r")
    Start-Sleep -Milliseconds 500
    for ($offset=0; $offset -lt $payload.Length; $offset+=768) {
        $count = [Math]::Min(768, $payload.Length-$offset)
        $serial.Write($payload.Substring($offset,$count)+"`r")
        Start-Sleep -Milliseconds 90
        if ($offset % (768*20) -eq 0) {
            Write-Output "Sent $offset / $($payload.Length) encoded bytes"
            $null = $serial.ReadExisting()
        }
    }
    $serial.Write("HDMI_PROBE_PAYLOAD_END`r")
    Start-Sleep -Milliseconds 500
    # Extract only our newly prepared relative paths after verifying integrity.
    $command = "echo '$expected  /tmp/hdmi_probe.tar.gz' | sha256sum -c - && tar -xzf /tmp/hdmi_probe.tar.gz -C /home/xilinx/lesion_fpga && echo HDMI_PROBE_TRANSFER_OK; stty echo"
    $serial.Write($command+"`r")
    Start-Sleep -Seconds 3
    $reply=$serial.ReadExisting()
    Write-Output $reply
    if ($reply -notmatch 'HDMI_PROBE_TRANSFER_OK') { throw 'Transfer not confirmed; do not load' }
} finally {
    if ($serial.IsOpen) {$serial.Close()}
}
