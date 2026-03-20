const { generate } = require('youtube-po-token-generator');

async function main() {
    try {
        console.log("Generating tokens...");
        const result = await generate();
        console.log("SUCCESS:");
        console.log("YOUTUBE_VISITOR_DATA=" + result.visitorData);
        console.log("YOUTUBE_PO_TOKEN=" + result.poToken);
    } catch (err) {
        console.error("ERROR:");
        console.error(err);
    }
}

main();
