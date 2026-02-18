export default {
    async scheduled(event, env, ctx) {
        const url = "https://hagsudfgiuaosihugfyusihadoibguyhiajofhgu.onrender.com";
        console.log(`Pinging Render service: ${url}`);

        // Using ctx.waitUntil to ensure the fetch completes before the worker terminates
        ctx.waitUntil(
            fetch(url)
                .then(res => console.log(`Response: ${res.status}`))
                .catch(err => console.error(`Ping failed: ${err.message}`))
        );
    },

    // Also handle manual pings via HTTP if needed
    async fetch(request, env, ctx) {
        return new Response("Render Keep-Alive Worker Active (Cron: Every 5 mins)");
    }
};
