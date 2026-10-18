Add-Type -AssemblyName System.Speech
$smartgateNarrator = New-Object System.Speech.Synthesis.SpeechSynthesizer
$smartgateScenes = Get-Content docs\mentor-video-scenes.json -Raw | ConvertFrom-Json
for ($sceneIndex = 0; $sceneIndex -lt $smartgateScenes.Count; $sceneIndex++) {
  $smartgateNarrator.SetOutputToWaveFile((Join-Path (Get-Location) "docs\mentor-video\voice-$sceneIndex.wav"))
  $smartgateNarrator.Speak($smartgateScenes[$sceneIndex].narration)
}
$smartgateNarrator.Dispose()
