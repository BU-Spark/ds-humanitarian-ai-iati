// Land points for the hero globe: a sunflower (golden-angle) spiral over the sphere, kept where it falls on land,
// tagged with the index of the hotspot country it falls in (0 = other land), plus a denser pass inside hotspot countries.
// Output: ../static/globe-pts.bin, Int16 triples (lat*100, lon*100, country index in data.json globe.countries order + 1).
//   cd fa26/web/globe && npm install && node genpts.mjs
import fs from 'fs';import {feature} from 'topojson-client';import {fileURLToPath} from 'url';
const HERE=fileURLToPath(new URL('.',import.meta.url));
const topo=JSON.parse(fs.readFileSync(HERE+'node_modules/world-atlas/countries-50m.json'));
const cs=feature(topo,topo.objects.countries).features;
const g=JSON.parse(fs.readFileSync(HERE+'../static/data.json')).globe;
const ours=Object.keys(g.countries);const alias={'Democratic Republic of the Congo':'Dem. Rep. Congo','South Sudan':'S. Sudan'};
const want=new Map(ours.map((c,i)=>[alias[c]||c,i+1]));
// polygons: {rings, bbox, ci}
const polys=[];for(const f of cs){if(f.properties.name==='Antarctica')continue;const ci=want.get(f.properties.name)||0;const geom=f.geometry;if(!geom)continue;
  const P=geom.type==='Polygon'?[geom.coordinates]:geom.coordinates;
  for(const rings of P){let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;for(const[x,y]of rings[0]){x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);}
    if(x1-x0>300)continue; polys.push({rings,b:[x0,y0,x1,y1],ci});}}
function inRing(r,x,y){let c=false;for(let i=0,j=r.length-1;i<r.length;j=i++){const[xi,yi]=r[i],[xj,yj]=r[j];if(((yi>y)!==(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi))c=!c;}return c;}
function hit(x,y){for(const p of polys){const b=p.b;if(x<b[0]||x>b[2]||y<b[1]||y>b[3])continue;if(inRing(p.rings[0],x,y)&&!p.rings.slice(1).some(h=>inRing(h,x,y)))return p.ci+1;}return 0;}
const N=+process.argv[2]||80000,ga=Math.PI*(3-Math.sqrt(5));const out=[];
for(let k=0;k<N;k++){const y=1-2*(k+.5)/N;const lat=Math.asin(y)*180/Math.PI;if(lat<-60)continue;let lon=((ga*k*180/Math.PI)%360);if(lon>180)lon-=360;
  const h=hit(lon,lat);if(!h)continue;out.push(Math.round(lat*100),Math.round(lon*100),h-1);}
// dense pass inside aid countries only
const M=400000;for(let k=0;k<M;k++){const y=1-2*(k+.5)/M;const lat=Math.asin(y)*180/Math.PI;if(lat<-30||lat>40)continue;let lon=((ga*k*180/Math.PI)%360);if(lon>180)lon-=360;
  const h=hit(lon,lat);if(h>1)out.push(Math.round(lat*100),Math.round(lon*100),h-1);}
fs.writeFileSync(HERE+'../static/globe-pts.bin',Buffer.from(new Int16Array(out).buffer));
const cnt={};for(let i=2;i<out.length;i+=3)cnt[out[i]]=(cnt[out[i]]||0)+1;console.log('land pts',out.length/3,JSON.stringify(cnt),ours);
