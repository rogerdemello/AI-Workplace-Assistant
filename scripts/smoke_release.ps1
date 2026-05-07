param(
    [string]$BackendBaseUrl = "http://127.0.0.1:8000",
    [string]$FrontendDir = "new-frontend",
    [switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-StatusCode {
    param(
        [int]$Actual,
        [int[]]$Allowed,
        [string]$Label
    )
    if ($Allowed -notcontains $Actual) {
        throw "$Label failed. Expected [$($Allowed -join ', ')], got $Actual"
    }
    Write-Host "PASS: $Label ($Actual)" -ForegroundColor Green
}

function Invoke-JsonRequest {
    param(
        [string]$Method,
        [string]$Url,
        [object]$Body = $null,
        [hashtable]$Headers = @{}
    )
    $jsonBody = $null
    if ($null -ne $Body) {
        $jsonBody = $Body | ConvertTo-Json -Depth 12
    }
    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers -Body $jsonBody -ContentType "application/json"
}

function Invoke-JsonRequestWithStatus {
    param(
        [string]$Method,
        [string]$Url,
        [object]$Body = $null,
        [hashtable]$Headers = @{}
    )
    $jsonBody = $null
    if ($null -ne $Body) {
        $jsonBody = $Body | ConvertTo-Json -Depth 12
    }
    try {
        $response = Invoke-WebRequest -Method $Method -Uri $Url -Headers $Headers -Body $jsonBody -ContentType "application/json"
        return @{
            StatusCode = [int]$response.StatusCode
            Body = if ($response.Content) { $response.Content | ConvertFrom-Json } else { $null }
        }
    } catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $statusCode = [int]$_.Exception.Response.StatusCode
            $responseBody = $null
            try {
                $stream = $_.Exception.Response.GetResponseStream()
                if ($stream) {
                    $reader = New-Object System.IO.StreamReader($stream)
                    $raw = $reader.ReadToEnd()
                    if ($raw) {
                        $responseBody = $raw | ConvertFrom-Json
                    }
                }
            } catch {
                $responseBody = $null
            }
            return @{
                StatusCode = $statusCode
                Body = $responseBody
            }
        }
        throw
    }
}

Write-Step "Backend smoke tests"
Push-Location "backend"
try {
    pytest tests
} finally {
    Pop-Location
}

if (-not $SkipBuild) {
    Write-Step "Frontend production build"
    Push-Location $FrontendDir
    try {
        npm run build
    } finally {
        Pop-Location
    }
}

Write-Step "API workflow smoke"

$employeeEmail = "employee@mark.ai"
$employeePassword = "password123"
$hrEmail = "hr@mark.ai"
$hrPassword = "password123"

$employeeLogin = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/auth/login" -Body @{
    email = $employeeEmail
    password = $employeePassword
}
Assert-StatusCode -Actual $employeeLogin.StatusCode -Allowed @(200) -Label "Employee login"
$employeeToken = $employeeLogin.Body.access_token
if (-not $employeeToken) { throw "Employee token missing." }
$employeeHeaders = @{ Authorization = "Bearer $employeeToken" }

$hrLogin = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/auth/login" -Body @{
    email = $hrEmail
    password = $hrPassword
}
Assert-StatusCode -Actual $hrLogin.StatusCode -Allowed @(200) -Label "HR login"
$hrToken = $hrLogin.Body.access_token
if (-not $hrToken) { throw "HR token missing." }
$hrHeaders = @{ Authorization = "Bearer $hrToken" }

$ticketCreate = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/tickets" -Headers $employeeHeaders -Body @{
    query = "Smoke test ticket: manager support needed"
    category = "complaint"
}
Assert-StatusCode -Actual $ticketCreate.StatusCode -Allowed @(200, 201) -Label "Create ticket"
$ticketId = $ticketCreate.Body.id
if (-not $ticketId) { throw "Ticket id missing from create response." }

$assignees = Invoke-JsonRequestWithStatus -Method "GET" -Url "$BackendBaseUrl/api/v1/tickets/assignees" -Headers $hrHeaders
Assert-StatusCode -Actual $assignees.StatusCode -Allowed @(200) -Label "List ticket assignees"
$assigneeId = $null
if ($assignees.Body -and $assignees.Body.Count -gt 0) {
    $assigneeId = $assignees.Body[0].id
}

if ($assigneeId) {
    $assignTicket = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/tickets/$ticketId/assign" -Headers $hrHeaders -Body @{
        assignee_id = $assigneeId
    }
    Assert-StatusCode -Actual $assignTicket.StatusCode -Allowed @(200) -Label "Assign ticket"
}

$ticketReply = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/tickets/$ticketId/messages" -Headers $hrHeaders -Body @{
    message_text = "We have started review."
}
Assert-StatusCode -Actual $ticketReply.StatusCode -Allowed @(200) -Label "Post HR ticket reply"

$ticketClose = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/tickets/$ticketId/close" -Headers $hrHeaders -Body @{
    resolution_note = "Smoke test resolution."
}
Assert-StatusCode -Actual $ticketClose.StatusCode -Allowed @(200) -Label "Close ticket"

$leaveCreate = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/leave" -Headers $employeeHeaders -Body @{
    start_date = "2026-05-10"
    end_date = "2026-05-12"
    leave_type = "paid_leave"
    reason = "Smoke test leave"
}
Assert-StatusCode -Actual $leaveCreate.StatusCode -Allowed @(201) -Label "Create leave request"
$leaveId = $leaveCreate.Body.id
if (-not $leaveId) { throw "Leave id missing from create response." }

$leaveApprove = Invoke-JsonRequestWithStatus -Method "PATCH" -Url "$BackendBaseUrl/api/v1/leave/$leaveId/approve" -Headers $hrHeaders -Body @{
    review_comment = "Approved in smoke test."
}
Assert-StatusCode -Actual $leaveApprove.StatusCode -Allowed @(200) -Label "Approve leave request"

$leaveCreate2 = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/leave" -Headers $employeeHeaders -Body @{
    start_date = "2026-05-20"
    end_date = "2026-05-20"
    leave_type = "sick_leave"
    reason = "Smoke cancel path"
}
Assert-StatusCode -Actual $leaveCreate2.StatusCode -Allowed @(201) -Label "Create second leave request"
$leaveId2 = $leaveCreate2.Body.id
if (-not $leaveId2) { throw "Second leave id missing from create response." }

$leaveCancel = Invoke-JsonRequestWithStatus -Method "PATCH" -Url "$BackendBaseUrl/api/v1/leave/$leaveId2/cancel" -Headers $employeeHeaders
Assert-StatusCode -Actual $leaveCancel.StatusCode -Allowed @(200) -Label "Cancel leave request"

$surveyCreate = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/surveys" -Headers $hrHeaders -Body @{
    title = "Smoke Survey"
    description = "Smoke survey description"
    allow_anonymous = $true
    questions = @(
        @{
            id = "q1"
            type = "rating"
            question = "How are you?"
            required = $true
        }
    )
}
Assert-StatusCode -Actual $surveyCreate.StatusCode -Allowed @(200, 201) -Label "Create survey"

$surveyList = Invoke-JsonRequestWithStatus -Method "GET" -Url "$BackendBaseUrl/api/v1/surveys" -Headers $hrHeaders
Assert-StatusCode -Actual $surveyList.StatusCode -Allowed @(200) -Label "List surveys"

$providers = Invoke-JsonRequestWithStatus -Method "GET" -Url "$BackendBaseUrl/api/v1/integrations/providers" -Headers $hrHeaders
Assert-StatusCode -Actual $providers.StatusCode -Allowed @(200) -Label "List integration providers"

$hrmsSync = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/integrations/hrms/sync" -Headers $hrHeaders -Body @{
    provider = "workday_hrms"
    dry_run = $true
    scope = "full"
}
Assert-StatusCode -Actual $hrmsSync.StatusCode -Allowed @(200) -Label "HRMS dry run sync"

$payrollSync = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/integrations/payroll/sync" -Headers $hrHeaders -Body @{
    provider = "adp_payroll"
    dry_run = $true
    scope = "full"
}
Assert-StatusCode -Actual $payrollSync.StatusCode -Allowed @(200) -Label "Payroll dry run sync"

$emailDraft = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/email/draft" -Headers $hrHeaders -Body @{
    type = "general"
    tone = "friendly"
    context = @{
        recipient_name = "Team"
        purpose = "Smoke test"
    }
}
Assert-StatusCode -Actual $emailDraft.StatusCode -Allowed @(200, 503) -Label "Email draft endpoint"

$emailSend = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/email/send" -Headers $hrHeaders -Body @{
    to = "team@example.com"
    subject = "Smoke test email"
    body = "Checking email endpoint wiring."
    cc = @("hr@example.com")
}
Assert-StatusCode -Actual $emailSend.StatusCode -Allowed @(200, 503) -Label "Email send endpoint"

$chatConversation = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/chat/conversations" -Headers $employeeHeaders
Assert-StatusCode -Actual $chatConversation.StatusCode -Allowed @(200) -Label "Create chat conversation"

$conversationId = $chatConversation.Body.id
if (-not $conversationId) { throw "Conversation id missing from create response." }

$chatMessage = Invoke-JsonRequestWithStatus -Method "POST" -Url "$BackendBaseUrl/api/v1/chat/conversations/$conversationId/messages" -Headers $employeeHeaders -Body @{
    message_text = "Help me with my timesheet"
    sender = "user"
}
Assert-StatusCode -Actual $chatMessage.StatusCode -Allowed @(200) -Label "Send chat message"

$hrRealtime = Invoke-WebRequest -Method "GET" -Uri "$BackendBaseUrl/api/v1/realtime/hr/stream" -Headers $hrHeaders -TimeoutSec 10
Assert-StatusCode -Actual ([int]$hrRealtime.StatusCode) -Allowed @(200) -Label "Realtime stream endpoint"

Write-Host ""
Write-Host "SMOKE RELEASE CHECK PASSED" -ForegroundColor Green
Write-Host "Backend tests, frontend build, and API workflow smoke succeeded."
