const {Readability} = require('@mozilla/readability');
const {JSDOM} = require('jsdom');
const {argv} = require('node:process');
const fs = require('fs');
const zlib = require('zlib');

const url = argv[2];
const inputPath = argv[3];
const outputPath = argv[4];

console.log(`input: ${inputPath}\noutput: ${outputPath}\n`);

fs.readFile(inputPath, (err, compressedData) => {
    if (err) {
        console.error('Error reading file:', err);
        return;
    }

    // Decompress the gzipped data
    zlib.gunzip(compressedData, (err, decompressedData) => {
        if (err) {
            console.error('Error decompressing file:', err);
            return;
        }

        // Convert buffer to string (assuming it's HTML text)
        const htmlContent = decompressedData.toString('utf8');

        const doc = new JSDOM(
            htmlContent,
            {url: url}
        );
        const reader = new Readability(doc.window.document);
        const parsed = reader.parse()

        // we just keep the body (reader.content)
        fs.writeFile(outputPath, parsed.content, (err) => {
            if (err) console.error('Error writing file:', err);
            else console.log('Successfully wrote file to', outputPath);
        });
    });
});

