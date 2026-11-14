import fs from 'node:fs/promises';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const out = new URL('./experimento_v2/', import.meta.url);
const data = JSON.parse(await fs.readFile(new URL('resumen_excel.json', out), 'utf8'));
const wb = Workbook.create();
for (const [name, rows] of Object.entries(data)) {
  const sh = wb.worksheets.add(name);
  sh.showGridLines = false;
  sh.getRangeByIndexes(0, 0, rows.length, rows[0].length).values = rows;
  const used = sh.getRangeByIndexes(0, 0, rows.length, rows[0].length);
  used.format.font = {name:'Arial', size:10};
  used.format.columnWidth = name === 'Resumen' ? 40 : 18;
  used.format.rowHeight = 23;
  sh.getRangeByIndexes(0, 0, 1, rows[0].length).format = {
    fill:'#20394A', font:{name:'Arial', size:10, bold:true, color:'#FFFFFF'},
    wrapText:true, rowHeight:52, horizontalAlignment:'center'
  };
  if (name === 'Resumen') {
    sh.getRange('B1:B17').format.columnWidth = 100;
    sh.getRange('B6:B11').setNumberFormat('0.00%');
  } else {
    sh.freezePanes.freezeRows(1);
    sh.getRangeByIndexes(1, 0, rows.length-1, rows[0].length).setNumberFormat('0.0000');
    if (name === 'Corridas') sh.getRange('A2:B49').setNumberFormat('0');
    for (let j=0;j<rows[0].length;j++) {
      if (['tn','fp','fn','tp','n'].includes(rows[0][j]))
        sh.getRangeByIndexes(1,j,rows.length-1,1).setNumberFormat('#,##0');
    }
    if (name === 'Calibracion') {
      sh.getRange('A2:B11').setNumberFormat('0.00%');
      sh.getRange('A1:B11').format.columnWidth=30;
    }
  }
}
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Resumen!A1:B17',tableMaxRows:17,tableMaxCols:2,maxChars:3500})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#N/A',options:{useRegex:true,maxResults:20},maxChars:1000})).ndjson);
for (const [name, rows] of Object.entries(data)) {
  const letters = n => { let s=''; while(n){ n--; s=String.fromCharCode(65+n%26)+s; n=Math.floor(n/26); } return s; };
  const preview = await wb.render({sheetName:name,range:`A1:${letters(rows[0].length)}${Math.min(rows.length,name === 'Resumen'?16:11)}`,scale:1,format:'png'});
  await fs.writeFile(new URL(`preview_${name}.png`,out),new Uint8Array(await preview.arrayBuffer()));
}
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(new URL('RESULTADOS.xlsx',out).pathname.replace(/^\/([A-Za-z]:)/,'$1'));
console.log('Excel exportado');
