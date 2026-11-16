"""Agensh-only text/function Responses -> Chat mapping; no network or secrets.

Unsupported modalities/built-in tools fail closed. previous_response_id state is
identity-bound and process-local, NOT durable production checkpoint custody.
"""
import copy
import json
import re
import secrets
import time

class Rejected(Exception):
    def __init__(self,code,status=400):self.code,self.status=code,status;super().__init__(code)

def need(value,code):
    if not value:raise Rejected(code)

def uid(prefix):return prefix+secrets.token_hex(16)
def wire(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def integer(x):return type(x)is int and x>=0

def text(value,allowed):
    if isinstance(value,str):return value
    need(type(value)is list,'UNSUPPORTED_CONTENT')
    parts=[]
    for p in value:
        need(type(p)is dict and p.get('type')in allowed and isinstance(p.get('text'),str),'TEXT_CONTENT_ONLY')
        parts.append(p['text'])
    return ''.join(parts)

def tools_to_chat(tools):
    need(type(tools)is list and len(tools)<=128,'TOOLS_BOUND')
    out=[];names=set()
    for tool in tools:
        need(type(tool)is dict and tool.get('type')=='function','FUNCTION_TOOLS_ONLY')
        need(set(tool)<={'type','name','description','parameters','strict'},'UNSUPPORTED_FUNCTION_FIELD')
        name=tool.get('name');need(isinstance(name,str)and re.fullmatch(r'[A-Za-z0-9_-]{1,64}',name),'FUNCTION_NAME')
        need(name not in names,'DUPLICATE_FUNCTION_NAME');names.add(name)
        f={k:copy.deepcopy(v)for k,v in tool.items()if k!='type'}
        need(type(f.get('parameters',{}))is dict,'FUNCTION_SCHEMA')
        out.append(dict(type='function',function=f))
    return out

def input_to_messages(value):
    if isinstance(value,str):return [dict(role='user',content=value)]
    need(type(value)is list and len(value)<=8192,'INPUT_ITEMS_BOUND')
    out=[]
    for item in value:
        need(type(item)is dict,'INPUT_ITEM_TYPE')
        kind=item.get('type','message')
        if kind=='message':
            role=item.get('role');need(role in ('system','developer','user','assistant'),'MESSAGE_ROLE')
            # GLM Chat does not promise a developer role. Preserve instruction
            # priority by mapping developer to system, never to user content.
            out.append(dict(role='system'if role=='developer'else role,
                content=text(item.get('content',''),('input_text','output_text'))))
        elif kind=='function_call':
            call=item.get('call_id');name=item.get('name');args=item.get('arguments')
            need(isinstance(call,str)and call and isinstance(name,str)and name and isinstance(args,str),'FUNCTION_CALL_FIELDS')
            tool=dict(id=call,type='function',function=dict(name=name,arguments=args))
            if out and out[-1]['role']=='assistant'and out[-1].get('tool_calls'):
                out[-1]['tool_calls'].append(tool)
            else:out.append(dict(role='assistant',content=None,tool_calls=[tool]))
        elif kind=='function_call_output':
            call=item.get('call_id');need(isinstance(call,str)and call,'TOOL_OUTPUT_CALL_ID')
            out.append(dict(role='tool',tool_call_id=call,content=text(item.get('output',''),('input_text','output_text'))))
        else:raise Rejected('UNSUPPORTED_INPUT_ITEM')
    return out

def validate_calls(messages):
    pending=set();seen=set()
    for message in messages:
        role=message['role']
        if role=='tool':
            call=message['tool_call_id'];need(call in pending,'UNKNOWN_OR_DUPLICATE_TOOL_RESULT');pending.remove(call)
        else:
            need(not pending,'MISSING_TOOL_RESULTS')
            calls=message.get('tool_calls',[])
            for call in calls:
                ident=call['id'];need(ident not in seen,'DUPLICATE_CALL_ID');seen.add(ident);pending.add(ident)
    need(not pending,'MISSING_TOOL_RESULTS')

def prepare(request,history,*,model,max_output):
    need(type(request)is dict,'JSON_OBJECT_REQUIRED')
    allowed={'model','input','instructions','previous_response_id','tools','tool_choice','parallel_tool_calls',
             'max_output_tokens','temperature','top_p','stream','metadata','store','reasoning','include',
             'text','truncation','background','service_tier','user','safety_identifier','prompt_cache_key'}
    need(not(set(request)-allowed),'UNSUPPORTED_REQUEST_FIELD')
    need(request.get('model')==model,'MODEL_NOT_CONFIGURED')
    need(type(request.get('stream',False))is bool,'STREAM_BOOLEAN')
    need(type(request.get('store',True))is bool,'STORE_BOOLEAN')
    metadata=request.get('metadata',{})
    need(type(metadata)is dict and len(metadata)<=16 and all(isinstance(k,str)and len(k)<=64 and isinstance(v,str)and len(v)<=512 for k,v in metadata.items()),'METADATA_BOUND')
    need(request.get('background',False)is False,'BACKGROUND_UNSUPPORTED')
    need(request.get('truncation','disabled')=='disabled','AUTOMATIC_TRUNCATION_UNSUPPORTED')
    need(request.get('service_tier','auto')in ('auto','default'),'SERVICE_TIER_UNSUPPORTED')
    # Reasoning replay/encryption is not a Chat capability. Effort is mapped;
    # summary/encrypted replay cannot silently be presented as supported.
    reasoning=request.get('reasoning')or {};need(type(reasoning)is dict,'REASONING_OBJECT')
    need(not(set(reasoning)-{'effort','summary'}),'UNSUPPORTED_REASONING_FIELD')
    need(reasoning.get('summary')in (None,'none'),'REASONING_SUMMARY_UNSUPPORTED')
    need(request.get('include',[])in ([],['reasoning.encrypted_content']),'UNSUPPORTED_INCLUDE')
    fmt=request.get('text')or {};need(type(fmt)is dict and not(set(fmt)-{'format','verbosity'}),'TEXT_OPTIONS')
    need(fmt.get('format',{'type':'text'})=={'type':'text'},'STRUCTURED_OUTPUT_UNSUPPORTED')
    need(fmt.get('verbosity')in (None,'medium'),'VERBOSITY_UNSUPPORTED')
    # None means no relay output cap/default. Preserve an explicit agent value.
    maximum=request['max_output_tokens'] if 'max_output_tokens' in request else max_output
    if maximum is not None:
        need(integer(maximum)and maximum>0,'OUTPUT_TOKEN_BOUND')
        if max_output is not None:need(maximum<=max_output,'OUTPUT_TOKEN_BOUND')
    else:need('max_output_tokens' not in request,'OUTPUT_TOKEN_BOUND')
    messages=copy.deepcopy(history)+input_to_messages(request.get('input',[]));validate_calls(messages)
    instructions=request.get('instructions')
    need(instructions is None or isinstance(instructions,str),'INSTRUCTIONS_STRING')
    chat=dict(model=model,messages=([dict(role='system',content=instructions)]if instructions is not None else [])+messages,
              stream=request.get('stream',False))
    if maximum is not None:chat['max_tokens']=maximum
    for key in ('temperature','top_p','parallel_tool_calls'):
        if key in request:chat[key]=request[key]
    if reasoning.get('effort')is not None:chat['reasoning_effort']=reasoning['effort']
    if 'tools'in request:chat['tools']=tools_to_chat(request['tools'])
    choice=request.get('tool_choice')
    if isinstance(choice,dict):
        need(set(choice)=={'type','name'}and choice['type']=='function','TOOL_CHOICE_FUNCTION')
        need(choice['name']in {t['function']['name']for t in chat.get('tools',[])},'TOOL_CHOICE_UNKNOWN')
        chat['tool_choice']=dict(type='function',function=dict(name=choice['name']))
    elif choice is not None:
        need(choice in ('none','auto','required'),'TOOL_CHOICE');chat['tool_choice']=choice
    if chat['stream']:chat['stream_options']=dict(include_usage=True)
    return chat,messages

def mapped_usage(usage):
    need(type(usage)is dict,'UPSTREAM_USAGE_MISSING')
    i,o,t=(usage.get(k)for k in ('prompt_tokens','completion_tokens','total_tokens'))
    need(all(integer(v)for v in (i,o,t))and t==i+o,'UPSTREAM_USAGE_INVALID')
    cached=(usage.get('prompt_tokens_details')or{}).get('cached_tokens',0)
    reasoning=(usage.get('completion_tokens_details')or{}).get('reasoning_tokens',0)
    need(integer(cached)and cached<=i and integer(reasoning)and reasoning<=o,'UPSTREAM_USAGE_DETAILS_INVALID')
    return dict(input_tokens=i,output_tokens=o,total_tokens=t,
                input_tokens_details=dict(cached_tokens=cached),output_tokens_details=dict(reasoning_tokens=reasoning))

def base_response(request,ident):
    return dict(id=ident,object='response',created_at=int(time.time()),status='in_progress',error=None,
                incomplete_details=None,model=request['model'],output=[],usage=None,
                instructions=request.get('instructions'),previous_response_id=request.get('previous_response_id'),
                tools=copy.deepcopy(request.get('tools',[])),tool_choice=request.get('tool_choice','auto'),
                parallel_tool_calls=request.get('parallel_tool_calls',True),metadata=request.get('metadata',{}),
                max_output_tokens=request.get('max_output_tokens'),store=request.get('store',True))

def finish_response(response,output,usage,reason):
    need(reason in ('stop','tool_calls','length','content_filter'),'UNSUPPORTED_FINISH_REASON')
    response.update(output=output,usage=mapped_usage(usage))
    if reason in ('length','content_filter'):
        response.update(status='incomplete',incomplete_details=dict(reason='max_output_tokens'if reason=='length'else'content_filter'))
    else:response['status']='completed'
    return response

def nonstream(response,chat):
    need(type(chat)is dict and type(chat.get('choices'))is list and len(chat['choices'])==1,'UPSTREAM_SINGLE_CHOICE')
    choice=chat['choices'][0];message=choice.get('message');need(type(message)is dict,'UPSTREAM_MESSAGE')
    need(message.get('role')=='assistant','UPSTREAM_ASSISTANT_REQUIRED')
    need(not message.get('refusal'),'UPSTREAM_REFUSAL_UNSUPPORTED')
    output=[];content=message.get('content')
    need(content is None or isinstance(content,str),'UPSTREAM_TEXT_ONLY')
    if content is not None:
        output.append(dict(id=uid('msg_'),type='message',role='assistant',status='completed',
            content=[dict(type='output_text',text=content,annotations=[],logprobs=[])]))
    calls=message.get('tool_calls')or[];need(type(calls)is list,'UPSTREAM_TOOL_CALLS')
    for call in calls:
        f=call.get('function',{});need(call.get('type')=='function'and isinstance(call.get('id'),str)and bool(call['id'])and
            isinstance(f.get('name'),str)and bool(f['name'])and isinstance(f.get('arguments'),str),'UPSTREAM_TOOL_FIELDS')
        output.append(dict(id=uid('fc_'),type='function_call',status='completed',call_id=call['id'],name=f['name'],arguments=f['arguments']))
    need(len({c['call_id']for c in output if c['type']=='function_call'})==len(calls),'UPSTREAM_DUPLICATE_CALL_ID')
    return finish_response(response,output,chat.get('usage'),choice.get('finish_reason'))

def assistant_history(response):
    message=dict(role='assistant',content=None);calls=[]
    for item in response['output']:
        if item['type']=='message':message['content']=''.join(p['text']for p in item['content'])
        elif item['type']=='function_call':calls.append(dict(id=item['call_id'],type='function',function=dict(name=item['name'],arguments=item['arguments'])))
    if calls:message['tool_calls']=calls
    return message

class StreamMapper:
    """Incremental Chat SSE -> Responses SSE. No synthetic token counts."""
    def __init__(self,response,emit):
        self.response,self.emit=response,emit;self.seq=0;self.items=[];self.tools={};self.text_index=None;self.finish=None;self.usage=None
        self.event('response.created',response=copy.deepcopy(response))
        self.event('response.in_progress',response=copy.deepcopy(response))
    def event(self,kind,**fields):
        self.emit(dict(type=kind,sequence_number=self.seq,**copy.deepcopy(fields)));self.seq+=1
    def add_text(self,delta):
        if self.text_index is None:
            self.text_index=len(self.items);item=dict(id=uid('msg_'),type='message',role='assistant',status='in_progress',content=[])
            self.items.append(item);self.event('response.output_item.added',output_index=self.text_index,item=item)
            item['content'].append(dict(type='output_text',text='',annotations=[],logprobs=[]))
            self.event('response.content_part.added',output_index=self.text_index,item_id=item['id'],content_index=0,part=item['content'][0])
        item=self.items[self.text_index];item['content'][0]['text']+=delta
        self.event('response.output_text.delta',output_index=self.text_index,item_id=item['id'],content_index=0,delta=delta,logprobs=[])
    def feed(self,chunk):
        need(type(chunk)is dict,'UPSTREAM_STREAM_CHUNK')
        if chunk.get('usage')is not None:self.usage=chunk['usage']
        choices=chunk.get('choices',[]);need(type(choices)is list and len(choices)<=1,'UPSTREAM_SINGLE_CHOICE')
        if not choices:return
        choice=choices[0];need(choice.get('index',0)==0,'UPSTREAM_SINGLE_CHOICE')
        delta=choice.get('delta',{});need(type(delta)is dict,'UPSTREAM_DELTA')
        need(not delta.get('refusal'),'UPSTREAM_REFUSAL_UNSUPPORTED')
        if delta.get('content')is not None:
            need(isinstance(delta['content'],str),'UPSTREAM_TEXT_ONLY');self.add_text(delta['content'])
        for call in delta.get('tool_calls')or[]:
            index=call.get('index');need(integer(index)and index<128,'UPSTREAM_TOOL_INDEX')
            f=call.get('function')or{}
            if index not in self.tools:
                need(call.get('type')in (None,'function')and isinstance(call.get('id'),str)and bool(call['id'])and
                    isinstance(f.get('name'),str)and bool(f['name']),'UPSTREAM_INITIAL_TOOL_ID_NAME_REQUIRED')
                item=dict(id=uid('fc_'),type='function_call',status='in_progress',call_id=call['id'],name=f['name'],arguments='')
                self.tools[index]=len(self.items);self.items.append(item)
                self.event('response.output_item.added',output_index=self.tools[index],item=item)
            item=self.items[self.tools[index]]
            need(call.get('id')in (None,item['call_id'])and f.get('name')in (None,'',item['name']),'UPSTREAM_TOOL_ID_NAME_CHANGED')
            args=f.get('arguments','');need(isinstance(args,str),'UPSTREAM_TOOL_ARGUMENTS')
            if args:
                item['arguments']+=args;self.event('response.function_call_arguments.delta',output_index=self.tools[index],item_id=item['id'],delta=args)
        if choice.get('finish_reason')is not None:
            need(self.finish is None,'UPSTREAM_MULTIPLE_FINISH');self.finish=choice['finish_reason']
    def done(self):
        need(self.finish is not None,'UPSTREAM_STREAM_NO_TERMINAL')
        need(len({self.items[j]['call_id']for j in self.tools.values()})==len(self.tools),'UPSTREAM_DUPLICATE_CALL_ID')
        for index,item in enumerate(self.items):
            item['status']='completed'
            if item['type']=='message':
                part=item['content'][0]
                self.event('response.output_text.done',output_index=index,item_id=item['id'],content_index=0,text=part['text'],logprobs=[])
                self.event('response.content_part.done',output_index=index,item_id=item['id'],content_index=0,part=part)
            else:self.event('response.function_call_arguments.done',output_index=index,item_id=item['id'],arguments=item['arguments'],name=item['name'])
            self.event('response.output_item.done',output_index=index,item=item)
        finish_response(self.response,self.items,self.usage,self.finish)
        return self.response
