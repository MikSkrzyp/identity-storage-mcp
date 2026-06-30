const STORE_PROMPT = "Before ending the session, store what happened using memory_store. Classify each memory: episodic for events/actions, semantic for durable facts, procedural for how-tos. One memory per distinct thing worth remembering. Skip idle chat."

export const IdentityStoragePlugin = async ({ client }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.deleted") {
        try {
          await client.tui.appendPrompt({ body: { text: STORE_PROMPT } })
        } catch (e) {
          await client.app.log({
            body: { service: "identity-storage", level: "error", message: `prompt injection failed: ${e}` },
          })
        }
      }
    },
  }
}