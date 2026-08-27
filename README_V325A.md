# v3.2.5a installer fix

Corrige únicamente el instalador de v3.2.5. El instalador anterior buscaba `def run_streamed(...)` con una expresión regular que solo soportaba correctamente una firma en una sola línea. En algunos árboles del proyecto la firma de `run_streamed` está partida en varias líneas, por lo que el instalador no la encontraba aunque la función existiera.

Esta revisión usa el AST de Python (`ast.parse`) para localizar exactamente `run_streamed`, con independencia de que la firma sea de una o varias líneas o tenga decoradores. Mantiene el mismo parche v3.2.5: backend `thread + queue` compatible con pipes de subprocess en Windows.

No cambia la Evidence Fabric ni la lógica de inteligencia. VERSION continúa siendo `3.2.5`.
