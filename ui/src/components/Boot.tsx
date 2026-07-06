import { useEffect, useState } from 'react'

/** ≤1s boot: "Myro online. Local. Listening▊" then fades. Click/keys skip it. */
export function Boot() {
  const [out, setOut] = useState(false)
  const [gone, setGone] = useState(false)
  useEffect(() => {
    const skip = () => setOut(true)
    const t1 = setTimeout(() => setOut(true), 900)
    window.addEventListener('keydown', skip, { once: true })
    window.addEventListener('pointerdown', skip, { once: true })
    return () => { clearTimeout(t1); window.removeEventListener('keydown', skip); window.removeEventListener('pointerdown', skip) }
  }, [])
  useEffect(() => {
    if (!out) return
    const t = setTimeout(() => setGone(true), 420)
    return () => clearTimeout(t)
  }, [out])
  if (gone) return null
  return (
    <div className={`boot ${out ? 'out' : ''}`} aria-hidden>
      <div className="bootline mono">
        <span className="k">Myro</span> online. Local. Listening<span className="bcur" />
      </div>
    </div>
  )
}
