<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import { RouterView } from 'vue-router'

const portalOrigin = (import.meta.env.VITE_PORTAL_URL || 'https://mikrotikke.netlify.app').replace(/\/$/, '')
const onboardingUrl = `${portalOrigin}/onboard`
const apiDocsUrl = import.meta.env.VITE_API_DOCS_URL || 'https://api.uzanet.co.ke/docs'

function linkText(anchor) {
  return (anchor?.textContent || '').replace(/\s+/g, ' ').trim()
}

function serviceTitle(anchor) {
  const card = anchor?.closest('#services .bg-white')
  return (card?.querySelector('h3')?.textContent || '').replace(/\s+/g, ' ').trim()
}

function destinationFor(anchor) {
  const text = linkText(anchor)
  if (text === 'Get Started' || text === 'Start onboarding' || text === 'Contact Sales') {
    return onboardingUrl
  }
  if (text === 'Try API' || text === 'View API Documentation' || text === 'View API docs') {
    return apiDocsUrl
  }
  if (text === 'Learn more') {
    const title = serviceTitle(anchor)
    if (title === 'ISP Software Suite') return onboardingUrl
    if (title === 'API as a Service') return apiDocsUrl
  }
  return ''
}

function rewriteProductLinks(root = document) {
  root.querySelectorAll('a').forEach((anchor) => {
    const destination = destinationFor(anchor)
    if (!destination) return
    anchor.setAttribute('href', destination)

    const title = serviceTitle(anchor)
    if (linkText(anchor) === 'Learn more' && title === 'ISP Software Suite') {
      anchor.childNodes.forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) node.textContent = ' Start onboarding '
      })
    } else if (linkText(anchor) === 'Learn more' && title === 'API as a Service') {
      anchor.childNodes.forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) node.textContent = ' View API docs '
      })
    } else if (linkText(anchor) === 'Contact Sales') {
      anchor.textContent = 'Start onboarding'
    }
  })
}

function alignHowItWorksCopy() {
  const section = document.querySelector('#how-it-works')
  if (!section) return
  section.querySelectorAll('h3').forEach((heading) => {
    const title = (heading.textContent || '').trim()
    const description = heading.parentElement?.querySelector('p')
    if (title === 'Sign Up') {
      heading.textContent = 'Sign In'
      if (description) description.textContent = 'Sign in to your Uzanet operator account and open guided router onboarding.'
    } else if (title === 'Provision') {
      heading.textContent = 'Connect Router'
      if (description) description.textContent = 'Name your MikroTik, choose the customer portal and generate the secure one-line setup command.'
    } else if (title === 'Go Live' && description) {
      description.textContent = 'Paste the command into RouterOS. Uzanet establishes the managed connection, claims the router and brings it into your dashboard.'
    }
  })
}

function handleProductClick(event) {
  const target = event.target instanceof Element ? event.target : null
  const anchor = target?.closest('a')
  if (!anchor) return
  const destination = destinationFor(anchor)
  if (!destination) return
  event.preventDefault()
  window.location.assign(destination)
}

let observer
onMounted(() => {
  rewriteProductLinks()
  alignHowItWorksCopy()
  document.addEventListener('click', handleProductClick, true)

  observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      mutation.addedNodes.forEach((node) => {
        if (node instanceof Element) rewriteProductLinks(node)
      })
    }
  })
  observer.observe(document.body, { childList: true, subtree: true })
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleProductClick, true)
  observer?.disconnect()
})
</script>

<template>
  <RouterView />
</template>
