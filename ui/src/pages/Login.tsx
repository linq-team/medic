import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/components/auth-provider'
import { createApiClient, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { KeyRound, AlertCircle, Loader2 } from 'lucide-react'

export function Login() {
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!apiKey.trim()) {
      setError('Please enter an API key')
      return
    }

    setIsLoading(true)

    try {
      // Create a temporary client with the provided API key to test it
      const testClient = createApiClient({ apiKey: apiKey.trim() })

      // Validate by making a request to the health endpoint
      await testClient.getHealth()

      // If successful, store the API key and redirect to dashboard
      login(apiKey.trim())
      navigate('/')
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError('Invalid API key. Please check your credentials.')
        } else if (err.status === 403) {
          setError('Access denied. Your API key does not have sufficient permissions.')
        } else {
          setError(`Authentication failed: ${err.message}`)
        }
      } else {
        setError('Unable to connect to the server. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md">
        {/* Logo and Title */}
        <div className="flex flex-col items-center mb-8">
          <img
            src="/assets/medic-icon-all-green.png"
            alt="Medic"
            className="h-16 w-16 mb-4"
          />
          <h1 className="text-3xl font-bold text-foreground">Medic</h1>
          <p className="text-muted-foreground mt-1">Service Health Monitoring</p>
        </div>

        {/* Login Card */}
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-xl">Sign In</CardTitle>
            <CardDescription>
              Enter your API key to access the dashboard
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Error Message */}
              {error && (
                <div className="flex items-center gap-2 p-3 text-sm text-destructive bg-destructive/10 rounded-md border border-destructive/20">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* API Key Input */}
              <div className="space-y-2">
                <label
                  htmlFor="api-key"
                  className="text-sm font-medium text-foreground"
                >
                  API Key
                </label>
                <div className="relative">
                  <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="api-key"
                    type="password"
                    placeholder="Enter your API key"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="pl-9"
                    disabled={isLoading}
                    autoFocus
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Contact your administrator if you don't have an API key.
                </p>
              </div>

              {/* Submit Button */}
              <Button
                type="submit"
                className="w-full"
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Validating...
                  </>
                ) : (
                  'Sign In'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Footer */}
        <p className="text-center text-xs text-muted-foreground mt-6">
          Medic UI &copy; {new Date().getFullYear()} Linq
        </p>
      </div>
    </div>
  )
}
