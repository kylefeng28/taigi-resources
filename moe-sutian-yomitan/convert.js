const { Dictionary, DictionaryIndex, TermEntry } = require('yomichan-dict-builder');
const fs = require('fs');

const ANCHOR = '\uFFF9';
const SEPARATOR = '\uFFFA';
const TERMINATOR = '\uFFFB';

function parseExample(raw) {
  // Format: {ANCHOR}hanzi{SEPARATOR}trs{TERMINATOR}translation
  const anchor = raw.indexOf(ANCHOR);
  const sep = raw.indexOf(SEPARATOR);
  const term = raw.indexOf(TERMINATOR);
  if (anchor === -1 || sep === -1 || term === -1) return null;
  return {
    hanzi: raw.slice(anchor + 1, sep),
    trs: raw.slice(sep + 1, term),
    translation: raw.slice(term + 1).trim(),
  };
}

function buildDefinitionContent(het) {
  const rows = [];

  if (het.reading) {
    const colors = { '白': 'green', '文': 'blue', '俗': 'orange', '替': 'gray' };
    rows.push({
      tag: 'div',
      content: [{
        tag: 'span',
        content: het.reading,
        style: { fontWeight: 'bold', color: colors[het.reading] ?? 'gray' },
      }],
    });
  }

  for (const def of het.definitions) {
    const defParts = [];

    if (def.type) {
      defParts.push({ tag: 'span', content: `【${def.type}】`, style: { fontWeight: 'bold' } });
    }
    defParts.push({ tag: 'span', content: def.def });

    rows.push({ tag: 'div', content: defParts });

    if (def.example) {
      for (const raw of def.example) {
        const ex = parseExample(raw);
        if (ex) {
          rows.push({
            tag: 'div',
            content: [
              { tag: 'span', content: ex.hanzi },
              { tag: 'span', content: ` ${ex.trs} `, style: { fontStyle: 'italic' } },
              { tag: 'span', content: ex.translation, style: { color: 'gray' } },
            ],
            style: { marginLeft: '1em', fontSize: '0.9em' },
          });
        } else {
          rows.push({ tag: 'div', content: raw, style: { marginLeft: '1em', fontSize: '0.9em' } });
        }
      }
    }
  }

  if (het.synonyms) {
    rows.push({ tag: 'div', content: `近義：${het.synonyms}`, style: { color: 'gray' } });
  }
  if (het.antonyms) {
    rows.push({ tag: 'div', content: `反義：${het.antonyms}`, style: { color: 'gray' } });
  }

  return { type: 'structured-content', content: { tag: 'div', content: rows } };
}

(async () => {
  const data = JSON.parse(fs.readFileSync('dict-twblg.json', 'utf8'));

  const dictionary = new Dictionary({ fileName: 'moe-minnan.zip' });

  const index = new DictionaryIndex()
    .setTitle('MoE Minnan (臺灣閩南語常用詞辭典)')
    .setRevision('2015-01-01')
    .setAuthor('Taiwan Ministry of Education')
    .setDescription('Taiwan Ministry of Education Dictionary of Frequently-Used Taiwanese Taigi (教育部臺灣台語常用詞辭典)')
    .setAttribution('https://sutian.moe.edu.tw/')
    .setUrl('https://github.com/kylefeng28/taigi-resources')
    .build();

  await dictionary.setIndex(index);

  for (const entry of data) {
    const readingOrder = { '替': 0, '白': 1, '文': 2, '': 3 };
    const heteronyms = [...entry.heteronyms].sort(
      (a, b) => (readingOrder[a.reading ?? ''] ?? 2) - (readingOrder[b.reading ?? ''] ?? 2)
    );
    for (const het of heteronyms) {
      const definition = buildDefinitionContent(het);

      const trs = het.trs.normalize('NFC');

      // Hanzi entry: hover over 佮意 → shows kah-ì
      await dictionary.addTerm(
        new TermEntry(entry.title).setReading(trs).addDetailedDefinition(definition).build()
      );

      // Romanization entry: hover over kah-ì → shows 佮意
      await dictionary.addTerm(
        new TermEntry(trs).setReading(entry.title).addDetailedDefinition(definition).build()
      );
    }
  }

  const stats = await dictionary.export('./dist');
  console.log('Done!');
  console.table(stats);
})();
