export const IdentityStoragePlugin = async ({ client, $ }) => {
  return {
    event: async ({ event }) => {
      // SessionStart equivalent: inject unprocessed raw memories
      if (event.type === "session.created") {
        try {
          const output = await $`uvx --from git+https://github.com/MikSkrzyp/identity-storage-mcp identity-storage-consolidate`.text()
          if (output.trim()) {
            await client.tui.appendPrompt({ body: { text: output.trim() } })
          }
        } catch (e) {
          await client.app.log({
            body: { service: "identity-storage", level: "error", message: `consolidate failed: ${e}` },
          })
        }
      }

      // Stop equivalent: store session transcript as raw memories
      if (event.type === "session.idle") {
        try {
          const sessionId = event.properties.sessionID || event.properties.info?.id
          if (!sessionId) return

          // Fetch messages from the session
          const messages = await client.session.messages({ path: { id: sessionId } })
          if (!messages.data || messages.data.length === 0) return

          // Build transcript-like payload for the ingestor
          const transcript = messages.data.map((entry) => {
            const role = entry.info?.role || "unknown"
            const parts = entry.parts || []
            const text = parts
              .filter((p) => p.type === "text")
              .map((p) => p.text || "")
              .join("\n")
              .trim()
            return { type: role, message: { role, content: text } }
          }).filter((m) => m.message.content.length > 0)

          if (transcript.length === 0) return

          // Write transcript to a temp file and pass to ingestor
          const tmpFile = `/tmp/identity-storage-opencode-${sessionId}.jsonl`
          const lines = transcript.map((m) => JSON.stringify(m)).join("\n")
          await $`echo ${lines} > ${tmpFile}`

          const payload = JSON.stringify({ transcript_path: tmpFile, session_id: sessionId })
          await $`echo ${payload} | uvx --from git+https://github.com/MikSkrzyp/identity-storage-mcp identity-storage-ingest --agent claude-code`

          await $`rm -f ${tmpFile}`
        } catch (e) {
          await client.app.log({
            body: { service: "identity-storage", level: "error", message: `ingest failed: ${e}` },
          })
        }
      }
    },
  }
}