## Resources for Taigi/Taiwanese/Minnan/Southern Hokkien 台語/閩南語/學習參看資料

## Anki Taigi Helper
[AnkiWeb link](https://ankiweb.net/shared/info/706708885) (id: 706708885)

This Anki addon automatically adds Tâi-Lô romanization and downloads audio from [Moedict](https://www.moedict.tw/) to make creating Anki notes for Taigi easier.

After entering the hanzi (漢字), the pronunciation and audio fields will be automatically filled out. If there are multiple matching options (e.g. a character with multiple 白/文/替 readings), the addon will prompt you to select the one you want.

To install this in Anki: Go to Tools > Add-Ons > Get Add-Ons > Enter code `706708885`.

Alternatively, git clone this repo and symlink the `./moedict_audio/` directory to the Anki addons directory (`~/.local/share/Anki2/addons21/ on Linux`, or `~/Library/Application\ Support/Anki2/addons21/` on macOs)

Configure the note type and fields as follows:
```
{
        "note_type": "Taigi",
        "source_field": "Hanzi",
        "tailo_field": "Pronunciation (Tai-lô)",
        "audio_field": "Audio",
        "auto_lookup": True,
}
```


## Resources for Getting Started

Please check out Aióng 阿勇's [Getting Started & Resource Guide](https://chiahpa.be/t/getting-started-resource-guide/262/1)!

Other resources to get started:
- [r/ohtaigi subreddit](https://www.reddit.com/r/ohtaigi)
- [Aiong's YouTube channel](https://www.youtube.com/channel/UC8Bj1AnLs3na054bM37BTNg)

### Romanization (Lô-má-jī 罗马字)
The most commonly used ones are [Pe̍h-ōe-jī (POJ)](https://en.wikipedia.org/wiki/Pe%CC%8Dh-%C5%8De-j%C4%AB), which was developed by missionaries in the 19th century and thus hundred years of history, and [Tâi-lô](https://en.wikipedia.org/wiki/T%C3%A2i-u%C3%A2n_L%C3%B4-m%C3%A1-j%C4%AB_Phing-im_Hong-%C3%A0n), which is the official system of Taiwan's Ministry of Education (MOE, 教育部).

### Dictionaries
- [MoE Dictionary of Frequently-Used Taiwanese Taigi (教育部臺灣台語常用詞辭典)](https://sutian.moe.edu.tw/zh-hant/) - Official dictionary of the Ministry of Education
- [MkDict](https://mkdict.net/) - multilingual dictionary that lets you search using English, Mandarin characters, or romanization (POJ or Tailo). References Maryknoll, MOE, Embree dictionaries and has audio examples
- [ChhoeTaigi 台語辭典](https://chhoe.taigi.info/) - most comprehensive Taigi dictionary; unfortunately doesn't seem to have audio or sentence examples
- [MoeDict 台語萌典](https://www.moedict.tw/') - "unofficial" version of the MOE dictionary with a nicer interface (make sure to click on the top left and select "臺灣台語" since MoeDict also supports Mandarin)
- [TaigiTube 台語水管](https://taigitube.com/) - not a real dictionary, but a website that lets you type in a word and finds clips from Taiwanese news/dramas/movies so that you can listen to how the world sounds in context in real spoken speech

## Tampermonkey/Greasemonkey user scripts
Install [Tampermonkey](https://www.tampermonkey.net/) for Chrome or [Greasemonkey](https://addons.mozilla.org/en-US/firefox/addon/greasemonkey/) for Firefox

- MoE Dictionary of Frequently-Used Taiwanese Taigi: [moe_taigi_sutian.user.js](https://raw.githubusercontent.com/kylefeng28/taigi-resources/refs/heads/main/moe_taigi_sutian.user.js): adds audio links to audio play buttons
